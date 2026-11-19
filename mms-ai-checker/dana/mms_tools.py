"""Python helpers for the Dana version of Module 1.

Dana does the checking logic (dana/mms_check.na). Python only does I/O:
load the sample application, read TXT fields, load the policy and run the
existing lexical policy retrieval. Everything is synthetic demo data.
"""

import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.rag import policy_bundle, retrieve  # noqa: E402
from app.security import normalize as _normalize  # noqa: E402
from app.security import suspicious as _suspicious  # noqa: E402

SAMPLES = ROOT / "samples" / "applications.json"
FIELDS = ["legal_name", "registration_number", "expires_on"]


def today_iso() -> str:
    return date.today().isoformat()


def _read_facts(text: str) -> dict:
    """Same rule as demo mode: a field counts only if it appears exactly once."""
    facts = {}
    for field in FIELDS:
        matches = re.findall(rf"(?m)^{field}:\s*([^\n]+)$", text)
        if len(matches) == 1:
            value = matches[0].strip()
            facts[field] = {
                "value": value,
                "quote": f"{field}: {value}",
                "confidence": 1.0,
            }
    return facts


def load_case(app_id: str, question: str, today: str = "") -> dict:
    """Return one application, its documents (with facts) and the policy."""
    today = today or today_iso()
    apps = json.loads(SAMPLES.read_text(encoding="utf-8"))
    item = next((a for a in apps if a["id"] == app_id), None)
    if item is None:
        raise ValueError(f"Unknown application: {app_id}")
    rules, md, digest = policy_bundle(item["tenant"], date.fromisoformat(today))
    documents = [
        {
            "id": d["id"],
            "kind": d["kind"],
            "version": d["version"],
            "verified_version": d["verified_version"],
            "verification": d["verification"],
            "facts": _read_facts(d["text"]),
        }
        for d in item["documents"]
    ]
    return {
        "app_id": app_id,
        "question": question,
        "today": today,
        "application": item["application"],
        "documents": documents,
        "policy": {"rules": rules, "md": md, "digest": digest},
    }


def normalize(value: str) -> str:
    return _normalize(value)


def suspicious(value: str) -> bool:
    return _suspicious(value)


def is_iso_date(value: str) -> bool:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def retrieve_policy(md: str, question: str, rule_ids: list) -> list:
    """Existing lexical RAG: every rule that fired is always included."""
    return retrieve(md, question, set(rule_ids))
