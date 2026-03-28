"""Tests for YAML rule loading."""

from pathlib import Path

from app.rule_loader import load_rules


def test_load_rules_contains_risks():
    root = Path(__file__).resolve().parent.parent
    rules = load_rules(root / "rules" / "risks.yaml")
    assert "RISK_02" in rules
    assert rules["RISK_02"].name
    assert len(rules) >= 20
