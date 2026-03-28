"""Load risk rules from YAML."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.models import RiskRule


def load_rules(path: Path) -> dict[str, RiskRule]:
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if not data or "risks" not in data:
        return {}
    out: dict[str, RiskRule] = {}
    for item in data["risks"]:
        rule = _parse_rule(item)
        out[rule.id] = rule
    return out


def _parse_rule(item: dict[str, Any]) -> RiskRule:
    return RiskRule(
        id=str(item["id"]),
        name=str(item.get("name", item["id"])),
        description=str(item.get("description", "")),
        category=str(item.get("category", "general")),
        default_severity=str(item.get("default_severity", "medium")),
        long_run_impact=str(item.get("long_run_impact", "")),
        signals=list(item.get("signals") or []),
        local_checks=list(item.get("local_checks") or []),
        llm_questions=list(item.get("llm_questions") or []),
        near_fix_templates=list(item.get("near_fix_templates") or []),
        long_term_fix_templates=list(item.get("long_term_fix_templates") or []),
        false_positive_notes=list(item.get("false_positive_notes") or []),
    )
