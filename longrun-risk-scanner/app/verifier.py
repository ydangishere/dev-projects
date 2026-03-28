"""Local verification: refine confidence using rule checks and context."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from app.models import (
    Confidence,
    ContextPack,
    Finding,
    FindingStatus,
    RiskRule,
    VerificationResult,
    VerifierSource,
)
from app.utils import read_text


def _sev_to_conf(rule: RiskRule, base: Confidence) -> Confidence:
    ds = rule.default_severity.lower()
    if ds == "high":
        return Confidence.HIGH if base == Confidence.MEDIUM else base
    if ds == "low":
        return Confidence.LOW if base == Confidence.MEDIUM else base
    return base


def verify_locally(finding: Finding, pack: ContextPack, rule: RiskRule) -> VerificationResult:
    """Apply conservative local checks; never alone 'confirms' without strong signals."""
    text = pack.nearby_lines.lower()
    evidence_bits: list[str] = []

    confirmed: Optional[bool] = None
    base = Confidence.MEDIUM

    # Rule-specific boosts
    if finding.risk_id == "RISK_02":
        if re.search(r"throw\s+new\s+\w+Exception", text):
            base = Confidence.LOW
            evidence_bits.append("catch rethrows wrapped exception nearby")
        if "catch_throwable" in finding.matched_signals or "Throwable" in finding.snippet:
            base = Confidence.HIGH
            evidence_bits.append("Throwable swallows errors broadly")

    if finding.risk_id == "RISK_03":
        if "empty_catch" in finding.matched_signals:
            base = Confidence.HIGH
            evidence_bits.append("empty catch block")

    if finding.risk_id == "RISK_06":
        if "timeout_config" in " ".join(pack.inferred_clues):
            confirmed = False
            evidence_bits.append("timeout/retry clues present in file header region")

    if finding.risk_id == "RISK_14":
        if re.search(r"idempot|dedup|unique", text):
            confirmed = False
            evidence_bits.append("idempotency/dedup hints found")

    if finding.risk_id == "RISK_17":
        if re.search(r"pageable|page\(|stream\(\)", text):
            base = Confidence.LOW
            evidence_bits.append("pagination/stream hints")

    conf = _sev_to_conf(rule, base)

    why = rule.long_run_impact
    fp = "; ".join(rule.false_positive_notes[:2]) if rule.false_positive_notes else "May be benign in tests or framework code."

    near = rule.near_fix_templates[0] if rule.near_fix_templates else "Add guards, timeouts, or explicit error handling."
    long_t = rule.long_term_fix_templates[0] if rule.long_term_fix_templates else "Improve architecture boundaries and observability."

    status = FindingStatus.VERIFYING
    if confirmed is False:
        status = FindingStatus.DISMISSED
        conf = Confidence.LOW
    elif confirmed is True:
        status = FindingStatus.CONFIRMED

    return VerificationResult(
        confirmed=confirmed,
        confidence=conf,
        why_risky_long_term=why,
        evidence_summary="; ".join(evidence_bits) or "Local pass: pattern + context alignment (conservative).",
        false_positive_possibility=fp,
        suggested_near_fix=near,
        suggested_long_term_fix=long_t,
        verifier_source=VerifierSource.LOCAL,
        raw={"status_hint": status.value},
    )


def merge_verification(
    local: VerificationResult,
    llm: Optional[VerificationResult],
) -> VerificationResult:
    if llm is None:
        return local
    # Prefer LLM for confirmed/uncertain narrative; bump verifier_source
    out = VerificationResult(
        confirmed=llm.confirmed if llm.confirmed is not None else local.confirmed,
        confidence=llm.confidence,
        why_risky_long_term=llm.why_risky_long_term or local.why_risky_long_term,
        evidence_summary=f"LLM: {llm.evidence_summary} | Local: {local.evidence_summary}",
        false_positive_possibility=llm.false_positive_possibility or local.false_positive_possibility,
        suggested_near_fix=llm.suggested_near_fix or local.suggested_near_fix,
        suggested_long_term_fix=llm.suggested_long_term_fix or local.suggested_long_term_fix,
        verifier_source=VerifierSource.BOTH,
        raw={"local": local.raw, "llm": llm.raw},
    )
    return out


def file_excerpt_for_finding(file_path: str, line_start: int, line_end: int, pad: int = 3) -> str:
    p = Path(file_path)
    lines = read_text(p).splitlines(keepends=True)
    a = max(1, line_start - pad)
    b = min(len(lines), line_end + pad)
    return "".join(lines[a - 1 : b])
