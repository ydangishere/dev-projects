"""Basic scanner smoke tests."""

from pathlib import Path

from app.rule_loader import load_rules
from app.file_scanner import scan_java_file


def test_sample_java_detects_multiple_risks():
    root = Path(__file__).resolve().parent.parent
    rules = load_rules(root / "rules" / "risks.yaml")
    sample = Path(__file__).parent / "fixtures" / "SampleRisks.java"
    cands = scan_java_file(sample, rules)
    ids = {c.risk_id for c in cands}
    assert "RISK_02" in ids
    assert "RISK_07" in ids
    assert "RISK_09" in ids
    assert "RISK_18" in ids or "RISK_08" in ids
