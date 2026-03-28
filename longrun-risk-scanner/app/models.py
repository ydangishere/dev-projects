"""Domain models for longrun-risk-scanner."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class FindingStatus(str, Enum):
    NEW = "new"
    VERIFYING = "verifying"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"


class Confidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class VerifierSource(str, Enum):
    LOCAL = "local"
    LLM = "llm"
    BOTH = "both"


@dataclass
class RiskRule:
    id: str
    name: str
    description: str
    category: str
    default_severity: str
    long_run_impact: str
    signals: list[str] = field(default_factory=list)
    local_checks: list[str] = field(default_factory=list)
    llm_questions: list[str] = field(default_factory=list)
    near_fix_templates: list[str] = field(default_factory=list)
    long_term_fix_templates: list[str] = field(default_factory=list)
    false_positive_notes: list[str] = field(default_factory=list)


@dataclass
class ScanSession:
    id: int
    root_path: str
    created_at: datetime
    updated_at: datetime
    label: str = ""
    status: str = "complete"


@dataclass
class Finding:
    id: int
    scan_id: int
    risk_id: str
    risk_name: str
    file_path: str
    line_start: int
    line_end: int
    snippet: str
    matched_signals: list[str]
    initial_reason: str
    evidence: dict[str, Any]
    status: FindingStatus
    confidence: Confidence
    severity: Severity
    false_positive_note: str
    long_run_impact: str
    near_fix: str
    long_term_fix: str
    verifier_source: VerifierSource
    created_at: datetime
    updated_at: datetime
    context_summary: str = ""


@dataclass
class ContextPack:
    """Compact bundle for local verification and optional LLM — never whole-project."""

    risk_rule: RiskRule
    file_path: str
    line_start: int
    line_end: int
    snippet: str
    enclosing_class: str
    enclosing_method: str
    nearby_lines: str
    annotations_in_scope: list[str]
    inferred_clues: list[str]
    inference_notes: list[str]
    project_references: list[str] = field(default_factory=list)
    rule_text_excerpt: str = ""


@dataclass
class VerificationResult:
    confirmed: Optional[bool]  # None = uncertain
    confidence: Confidence
    why_risky_long_term: str
    evidence_summary: str
    false_positive_possibility: str
    suggested_near_fix: str
    suggested_long_term_fix: str
    verifier_source: VerifierSource
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReportSummary:
    scan_id: int
    root_path: str
    created_at: datetime
    total_findings: int
    by_status: dict[str, int]
    by_severity: dict[str, int]
    findings_preview: list[dict[str, Any]]


@dataclass
class CandidateFinding:
    """Pre-persistence detection result (risk candidate)."""

    risk_id: str
    line_start: int
    line_end: int
    snippet: str
    matched_signals: list[str]
    initial_reason: str
    evidence: dict[str, Any]
