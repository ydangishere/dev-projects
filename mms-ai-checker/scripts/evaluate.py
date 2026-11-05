"""Reproducible synthetic rule evaluation; not a live Gemini accuracy benchmark."""

import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.engine import evaluate  # noqa: E402
from app.providers import Source, extract_demo  # noqa: E402
from app.rag import policy_bundle  # noqa: E402

EXPECTED = {
    "APP-DEMO-001": ["missing_document", "unverified_version", "expired"],
    "APP-DEMO-002": ["mismatch"],
    "APP-DEMO-003": [],
}
rules, _, digest = policy_bundle("pvcb", date(2026, 11, 5))
results = []
for item in json.loads((ROOT / "samples/applications.json").read_text()):
    if item["id"] not in EXPECTED:
        continue
    docs = item["documents"]
    extracted = {
        d["id"]: extract_demo(Source(d["text"].encode(), "text/plain", 1)) for d in docs
    }
    actual = [
        f.code
        for f in evaluate(
            item["application"], docs, extracted, rules, date(2026, 11, 5), "demo"
        )
    ]
    results.append(
        {
            "application_id": item["id"],
            "expected": EXPECTED[item["id"]],
            "actual": actual,
            "exact_match": Counter(actual) == Counter(EXPECTED[item["id"]]),
        }
    )
report = {
    "scope": "synthetic deterministic rules only; no real documents or live Gemini",
    "review_date": "2026-11-05",
    "policy_sha256": digest,
    "cases": results,
    "exact_match_cases": sum(r["exact_match"] for r in results),
    "total_cases": len(results),
    "production_accuracy": "not measured",
}
(ROOT / "docs").mkdir(exist_ok=True)
(ROOT / "docs/evaluation.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2) + "\n"
)
print(json.dumps(report, ensure_ascii=False, indent=2))
if not all(r["exact_match"] for r in results):
    raise SystemExit(1)
