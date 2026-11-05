import hashlib
import re
from pathlib import Path

import yaml

POLICIES = Path(__file__).resolve().parents[1] / "policies"


def policy_bundle(tenant: str, today):
    raw = (POLICIES / "rules.yaml").read_bytes()
    rules = yaml.safe_load(raw)
    md = (POLICIES / "approval.md").read_text(encoding="utf-8")
    if (
        rules["tenant"] != tenant
        or not rules["effective_from"] <= today.isoformat() <= rules["effective_to"]
    ):
        raise ValueError("No applicable policy; manual review required")
    digest = hashlib.sha256(raw + md.encode()).hexdigest()
    return rules, md, digest


def retrieve(md: str, query: str, required_rule_ids: set[str]):
    """Local lexical RAG: rank sections, always include every executed rule.

    Small policy collection needs no vector DB. Query cannot suppress a rule.
    """
    terms = set(re.findall(r"\w+", query.casefold()))
    sections = []
    for section in re.split(r"(?m)^## ", md)[1:]:
        rule = section.split()[0]
        score = len(terms & set(re.findall(r"\w+", section.casefold())))
        if rule in required_rule_ids or score:
            sections.append({"rule": rule, "text": section.strip(), "score": score})
    return sorted(sections, key=lambda s: (-s["score"], s["rule"]))
