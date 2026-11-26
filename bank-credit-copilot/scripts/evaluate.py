"""Offline evaluation against eval/golden.json.

Measures extraction accuracy, rule/verdict accuracy and policy-retrieval accuracy
(including refusals for off-topic questions). Writes eval/results.json and exits with
status 1 if any metric is below its threshold.

    python scripts/evaluate.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.llm import LLMConfig  # noqa: E402
from app.pipeline import CreditCopilot, Settings  # noqa: E402

THRESHOLDS = {"field_accuracy": 1.0, "rule_accuracy": 1.0, "verdict_accuracy": 1.0, "policy_accuracy": 0.9}


def main() -> int:
    golden = json.loads((ROOT / "eval" / "golden.json").read_text(encoding="utf-8"))
    settings = Settings()
    settings.audit_path = Path(tempfile.mkdtemp()) / "audit.jsonl"
    copilot = CreditCopilot(settings, LLMConfig())  # always offline: reproducible
    as_of = date.fromisoformat(golden["as_of"])
    field_hits = field_total = rule_hits = rule_total = verdict_hits = 0
    failures: list[str] = []

    for case in golden["cases"]:
        result = copilot.assess_files(copilot.sample_files(case["case_id"]), as_of=as_of, case_id=case["case_id"])
        verdict_hits += result["verdict"] == case["verdict"]
        if result["verdict"] != case["verdict"]:
            failures.append(f"{case['case_id']} verdict {result['verdict']} != {case['verdict']}")
        statuses = {r["rule_id"]: r["status"] for r in result["rules"]}
        for rule_id, expected in case["rules"].items():
            rule_total += 1
            rule_hits += statuses.get(rule_id) == expected
            if statuses.get(rule_id) != expected:
                failures.append(f"{case['case_id']} {rule_id} {statuses.get(rule_id)} != {expected}")
        fields = result["extraction"]["fields"]
        for key, expected in case["fields"].items():
            doc_type, name = key.split(".")
            got = fields.get(doc_type, {}).get(name, {}).get("value")
            field_total += 1
            field_hits += got == expected
            if got != expected:
                failures.append(f"{case['case_id']} field {key}: {got!r} != {expected!r}")
        field_total += 1
        got_credits = len(result["extraction"]["salary_credits"])
        field_hits += got_credits == case["salary_credits"]
        if got_credits != case["salary_credits"]:
            failures.append(f"{case['case_id']} salary credits {got_credits} != {case['salary_credits']}")

    policy_hits = 0
    for item in golden["policy_questions"]:
        answer = copilot.ask_policy(item["q"])
        got = answer["cited"][0] if answer["cited"] else None
        policy_hits += got == item["expected"]
        if got != item["expected"]:
            failures.append(f"policy '{item['q']}': {got} != {item['expected']}")

    metrics = {
        "field_accuracy": round(field_hits / field_total, 3),
        "rule_accuracy": round(rule_hits / rule_total, 3),
        "verdict_accuracy": round(verdict_hits / len(golden["cases"]), 3),
        "policy_accuracy": round(policy_hits / len(golden["policy_questions"]), 3),
    }
    report = {"metrics": metrics, "thresholds": THRESHOLDS, "failures": failures,
              "cases": len(golden["cases"]), "policy_questions": len(golden["policy_questions"]),
              "mode": "offline (regex extraction, BM25 retrieval, template memo)"}
    (ROOT / "eval" / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                                encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if all(metrics[k] >= v for k, v in THRESHOLDS.items()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
