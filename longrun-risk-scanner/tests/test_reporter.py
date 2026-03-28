"""Reporter tests."""

from datetime import datetime, timezone

from app.models import (
    Confidence,
    Finding,
    FindingStatus,
    ReportSummary,
    ScanSession,
    Severity,
    VerifierSource,
)
from app.reporter import build_report_summary, findings_to_jsonable, terminal_summary


def test_report_summary():
    sess = ScanSession(
        id=1,
        root_path="/proj",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    f = Finding(
        id=1,
        scan_id=1,
        risk_id="RISK_02",
        risk_name="x",
        file_path="/a/B.java",
        line_start=1,
        line_end=2,
        snippet="",
        matched_signals=[],
        initial_reason="",
        evidence={},
        status=FindingStatus.NEW,
        confidence=Confidence.LOW,
        severity=Severity.MEDIUM,
        false_positive_note="",
        long_run_impact="",
        near_fix="",
        long_term_fix="",
        verifier_source=VerifierSource.LOCAL,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    summary = build_report_summary(sess, [f])
    assert summary.total_findings == 1
    js = findings_to_jsonable([f])
    assert js[0]["risk_id"] == "RISK_02"
    out = terminal_summary(sess, [f])
    assert "B.java" in out
