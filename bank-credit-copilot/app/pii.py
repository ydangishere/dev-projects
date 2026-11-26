"""Mask personal data before any text leaves the service (policy Điều 7).

Uses Microsoft Presidio with Vietnamese recognisers:
* CCCD / ID numbers (12 digits), bank account numbers, Vietnamese phone numbers (regex);
* names already known from the file (deny-list built from the extracted names);
* person names found by a multilingual spaCy NER model, when it is installed.

Masking is reversible inside the request: each value becomes a placeholder such as
<CCCD_1> or <PERSON_1>, the model only ever sees placeholders, and `unmask` restores the
original values in the model's answer. If Presidio is not installed, a regex fallback
masks ID and account numbers so nothing breaks.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from .observability import PII_MASKED

LANG = "vi"
ID_REGEX = r"(?<!\d)\d{12}(?!\d)"
ACCOUNT_REGEX = r"(?<!\d)\d{4}[ .-]\d{4}[ .-]\d{4}(?!\d)|(?<!\d)\d{9,11}(?!\d)"
PHONE_REGEX = r"(?<!\d)(?:\+84|0)(?:3|5|7|8|9)\d{8}(?!\d)"

_ENGINE = None
_ENGINE_ERROR: str | None = None


def _build_presidio():
    from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer, RecognizerRegistry
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    model = os.getenv("PII_SPACY_MODEL", "xx_ent_wiki_sm")
    provider = NlpEngineProvider(nlp_configuration={
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": LANG, "model_name": model}],
        "ner_model_configuration": {"model_to_presidio_entity_mapping": {"PER": "PERSON", "PERSON": "PERSON"}},
    })
    nlp_engine = provider.create_engine()
    registry = RecognizerRegistry(supported_languages=[LANG])
    registry.add_recognizer(PatternRecognizer(
        supported_entity="VN_ID", supported_language=LANG, name="VietnamIdRecognizer",
        patterns=[Pattern("cccd_12_digits", ID_REGEX, 0.9)],
        context=["cccd", "căn cước", "định danh", "cmnd"]))
    registry.add_recognizer(PatternRecognizer(
        supported_entity="VN_BANK_ACCOUNT", supported_language=LANG, name="VietnamAccountRecognizer",
        patterns=[Pattern("account", ACCOUNT_REGEX, 0.6)], context=["tài khoản", "stk", "số tk"]))
    registry.add_recognizer(PatternRecognizer(
        supported_entity="VN_PHONE", supported_language=LANG, name="VietnamPhoneRecognizer",
        patterns=[Pattern("phone", PHONE_REGEX, 0.7)]))
    try:
        from presidio_analyzer.predefined_recognizers import SpacyRecognizer

        registry.add_recognizer(SpacyRecognizer(supported_language=LANG, supported_entities=["PERSON"]))
    except Exception:  # noqa: BLE001 - NER is a bonus; patterns + deny-list still work
        pass
    return AnalyzerEngine(nlp_engine=nlp_engine, registry=registry, supported_languages=[LANG])


def engine_name() -> str:
    """'presidio' when Presidio loaded, otherwise 'regex-fallback' (with the reason)."""
    global _ENGINE, _ENGINE_ERROR
    if _ENGINE is None and _ENGINE_ERROR is None:
        if os.getenv("PII_ENGINE", "auto") == "regex":
            _ENGINE_ERROR = "disabled by PII_ENGINE=regex"
        else:
            try:
                _ENGINE = _build_presidio()
            except Exception as exc:  # noqa: BLE001
                _ENGINE_ERROR = f"{type(exc).__name__}: {exc}"[:200]
    return "presidio" if _ENGINE is not None else "regex-fallback"


@dataclass
class Masker:
    """Keeps placeholder <-> original mappings for one request."""

    known_names: list[str] = field(default_factory=list)
    mapping: dict[str, str] = field(default_factory=dict)      # placeholder -> original
    _reverse: dict[tuple[str, str], str] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)

    def _placeholder(self, entity: str, original: str) -> str:
        key = (entity, re.sub(r"\s+", " ", original.strip().lower()))
        if key not in self._reverse:
            short = {"VN_ID": "CCCD", "VN_BANK_ACCOUNT": "STK", "VN_PHONE": "SDT", "PERSON": "PERSON"}.get(entity, entity)
            index = sum(1 for k in self._reverse if k[0] == entity) + 1
            placeholder = f"<{short}_{index}>"
            self._reverse[key] = placeholder
            self.mapping[placeholder] = original.strip()
            self.counts[entity] = self.counts.get(entity, 0) + 1
            PII_MASKED.labels(entity=entity).inc()
        return self._reverse[key]

    def _spans(self, text: str) -> list[tuple[int, int, str]]:
        spans: list[tuple[int, int, str]] = []
        if engine_name() == "presidio":
            from presidio_analyzer import PatternRecognizer

            deny = [n for n in self.known_names if n and len(n) > 3]
            extra = [PatternRecognizer(supported_entity="PERSON", supported_language=LANG, deny_list=deny,
                                       name="KnownApplicantNames")] if deny else []
            results = _ENGINE.analyze(text=text, language=LANG, ad_hoc_recognizers=extra, score_threshold=0.5)
            spans = [(r.start, r.end, r.entity_type) for r in results]
        else:
            for regex, entity in ((ID_REGEX, "VN_ID"), (ACCOUNT_REGEX, "VN_BANK_ACCOUNT"), (PHONE_REGEX, "VN_PHONE")):
                spans += [(m.start(), m.end(), entity) for m in re.finditer(regex, text)]
            for name in self.known_names:
                if name and len(name) > 3:
                    spans += [(m.start(), m.end(), "PERSON")
                              for m in re.finditer(re.escape(name), text, flags=re.IGNORECASE)]
        # keep the longest non-overlapping spans
        spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
        kept: list[tuple[int, int, str]] = []
        for span in spans:
            if not kept or span[0] >= kept[-1][1]:
                kept.append(span)
        return kept

    def mask(self, text: str) -> str:
        out, last = [], 0
        for start, end, entity in self._spans(text):
            out.append(text[last:start])
            out.append(self._placeholder(entity, text[start:end]))
            last = end
        out.append(text[last:])
        return "".join(out)

    def unmask(self, text: str) -> str:
        for placeholder, original in self.mapping.items():
            text = text.replace(placeholder, original)
        return text


def mask_for_log(text: str) -> str:
    """One-way masking for logs: keep the last 3 digits of long numbers."""
    return re.sub(r"\d[\d .-]{7,}\d", lambda m: "*" * 6 + re.sub(r"\D", "", m.group(0))[-3:], text)


def status() -> dict:
    name = engine_name()
    return {"engine": name, "detail": _ENGINE_ERROR}
