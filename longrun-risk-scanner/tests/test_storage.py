"""SQLite storage tests."""

from pathlib import Path

from app.models import Confidence, FindingStatus, Severity, VerifierSource
from app.storage import Storage


def test_storage_roundtrip(tmp_path):
    db = tmp_path / "t.db"
    s = Storage(db)
    s.init_schema()
    sid = s.create_scan_session(str(tmp_path))
    fid = s.insert_finding(
        scan_id=sid,
        risk_id="RISK_02",
        risk_name="Overly broad catch",
        file_path="/x/Foo.java",
        line_start=1,
        line_end=2,
        snippet="catch (Exception e) {}",
        matched_signals=["catch_exception"],
        initial_reason="test",
        evidence={},
        status=FindingStatus.NEW,
        confidence=Confidence.LOW,
        severity=Severity.MEDIUM,
    )
    f = s.get_finding(fid)
    assert f is not None
    assert f.risk_id == "RISK_02"
    rows = s.list_findings(scan_id=sid)
    assert len(rows) == 1
