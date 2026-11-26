"""Smoke test: run one messy file and one policy question through the LiteLLM proxy.

Exits 1 unless the model behind the proxy actually filled at least one field.
"""

from __future__ import annotations

import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.pipeline import CreditCopilot, Settings  # noqa: E402


def main() -> int:
    settings = Settings.from_env()
    settings.audit_path = Path(tempfile.mkdtemp()) / "audit.jsonl"
    copilot = CreditCopilot(settings)
    result = copilot.assess_files(copilot.sample_files("HS-005"), as_of=date(2026, 11, 26), case_id="HS-005")
    llm_fields = [f"{dt}.{k}" for dt, fs in result["extraction"]["fields"].items()
                  for k, ev in fs.items() if ev["method"] == "llm"]
    answer = copilot.ask_policy("DTI tối đa là bao nhiêu?")
    print("model:", copilot.llm.model)
    print("verdict:", result["verdict"], "| fields filled by the model via proxy:", len(llm_fields))
    print("memo source:", result["narrative"]["source"], "|", result["narrative"].get("fallback_reason"))
    print("policy answer:", answer["source"], answer["cited"], answer["answer"][:120])
    return 0 if llm_fields else 1


if __name__ == "__main__":
    raise SystemExit(main())
