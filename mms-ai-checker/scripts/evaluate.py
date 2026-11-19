"""Reproducible synthetic rule evaluation; not a live Gemini accuracy benchmark."""

import json
import os
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.engine import evaluate  # noqa: E402
from app.providers import Source, extract_demo  # noqa: E402
from app.rag import policy_bundle  # noqa: E402
from app.retrieval_eval import run as run_retrieval  # noqa: E402

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
    "policy_retrieval": {"local-hashing": run_retrieval()},
}
try:
    from app.retrieval import FastEmbedEmbedder, HybridRetriever  # noqa: E402

    semantic = HybridRetriever(FastEmbedEmbedder())
except ImportError:
    report["policy_retrieval"]["fastembed"] = (
        "not installed; pip install -r requirements-semantic.txt to include it"
    )
else:
    report["policy_retrieval"]["fastembed"] = run_retrieval(retriever=semantic)
load_dotenv(ROOT / ".env")
if os.getenv("GEMINI_API_KEY"):
    from app.retrieval import GeminiEmbedder, HybridRetriever  # noqa: E402

    report["policy_retrieval"]["gemini"] = run_retrieval(
        retriever=HybridRetriever(GeminiEmbedder())
    )
else:
    report["policy_retrieval"]["gemini"] = "skipped; set GEMINI_API_KEY to include it"
(ROOT / "docs").mkdir(exist_ok=True)
(ROOT / "docs/evaluation.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
)
print(json.dumps(report, ensure_ascii=False, indent=2))
if not all(r["exact_match"] for r in results):
    raise SystemExit(1)
# Gate only on the dev split. The holdout split is reported, never tuned against.
dev = report["policy_retrieval"]["local-hashing"]["dev"]
if any(dev["hybrid"][m] < dev["lexical_baseline"][m] for m in dev["hybrid"]):
    raise SystemExit("Hybrid retrieval regressed below the lexical baseline on dev")
