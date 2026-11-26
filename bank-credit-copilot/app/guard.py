"""Guardrails around the language model.

1. Document injection scan (deterministic): uploaded files are untrusted. Lines that try
   to instruct the AI ("bỏ qua mọi hướng dẫn…", "ignore previous instructions…") are
   flagged, removed from what the model sees, and logged as a security event.
2. Llama Guard (optional, GUARD_MODEL): a safety classifier model screens policy
   questions before they reach the LLM and LLM answers before they reach the officer.

Neither can change a credit decision: pass/fail is computed by rules, not by the model.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from .observability import GUARD_EVENTS, traced
from .textutil import norm

_INJECTION_PATTERNS = [
    r"bo qua (moi |tat ca |cac )?(huong dan|chi dan|quy tac|lenh)",
    r"(quen|phot lo) (het |moi )?(huong dan|quy tac)",
    r"(he thong|tro ly|mo hinh) ai",
    r"ket luan (ho so nay )?(la )?du dieu kien",
    r"danh gia (ho so nay )?(la )?(du dieu kien|dat)",
    r"phe duyet (ngay )?ho so nay",
    r"ignore (all |any |the )?(previous|prior|above) (instructions|rules)",
    r"disregard (all |the )?(previous|prior|above)",
    r"system prompt",
    r"you are now",
    r"approve this (application|loan)",
]


@dataclass
class GuardResult:
    safe: bool
    category: str | None = None
    source: str = "disabled"


def injection_lines(lines: list[str]) -> list[int]:
    """Indexes of lines that look like instructions aimed at the AI."""
    flagged = []
    for index, line in enumerate(lines):
        text = norm(line)
        if any(re.search(p, text) for p in _INJECTION_PATTERNS):
            flagged.append(index)
    if flagged:
        GUARD_EVENTS.labels(stage="document_injection", result="flagged").inc(len(flagged))
    return flagged


def guard_model() -> str:
    return os.getenv("GUARD_MODEL", "").strip()


@traced("llama-guard", as_type="generation")
def moderate(text: str, stage: str) -> GuardResult:
    """Ask Llama Guard whether `text` is safe. Fails open with source='error' if it is down."""
    model = guard_model()
    if not model:
        return GuardResult(True)
    try:
        import litellm

        response = litellm.completion(
            model=model, messages=[{"role": "user", "content": text[:4000]}], temperature=0,
            api_base=os.getenv("GUARD_API_BASE") or os.getenv("LLM_API_BASE") or None,
            api_key=os.getenv("GUARD_API_KEY") or os.getenv("LLM_API_KEY") or None,
            timeout=float(os.getenv("GUARD_TIMEOUT", "60")), max_tokens=20)
        verdict = (response.choices[0].message.content or "").strip().lower()
    except Exception:  # noqa: BLE001 - the guard must not take the service down
        GUARD_EVENTS.labels(stage=stage, result="error").inc()
        return GuardResult(True, source="error")
    if verdict.startswith("unsafe"):
        category = verdict.split()[1].upper() if len(verdict.split()) > 1 else "UNSAFE"
        GUARD_EVENTS.labels(stage=stage, result="unsafe").inc()
        return GuardResult(False, category, "llama-guard")
    GUARD_EVENTS.labels(stage=stage, result="safe").inc()
    return GuardResult(True, source="llama-guard")
