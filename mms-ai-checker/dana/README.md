# Module 1 in Dana (prototype)

The document-checking flow of MMS AI Checker, rewritten in [Dana](https://github.com/aitomatic/dana), Aitomatic's agent programming language.

**Rules find the problems → policy retrieval finds the matching sections → the LLM explains → an employee decides.**

| File | Role |
|---|---|
| `mms_check.na` | Dana: rules R1–R6, policy lookup, LLM explanation, workflow `run_rules \| find_policy \| explain` |
| `mms_tools.py` | Python I/O only: load sample application, read TXT fields, load policy, reuse `app/rag.py` retrieval |

## Run

```bash
pip install dana          # plus the repo's requirements.txt
# configure an LLM provider key for Dana's reason() (see Dana docs)
cd mms-ai-checker/dana
dana run mms_check.na
```

## Expected findings (sample data, check date 2026-11-16)

| Application | Findings from rules |
|---|---|
| APP-DEMO-001 | R1 missing `bank_confirmation` (blocker) · R2 `DOC-001-ID` expired (blocker) · R4 `DOC-001-LIC` unverified version |
| APP-DEMO-002 | R3 `DOC-002-BANK` legal_name mismatch |
| APP-DEMO-003 | none |

## Status and limits

- **Not yet executed with the Dana runtime.** The rule logic was checked with a line-by-line Python mirror, which produces exactly the same findings as `app/engine.py` for all three samples. Dana syntax follows the public docs (v0.5–0.6) and may need small fixes on first run.
- Demo mode only (synthetic TXT, no OCR), so R7 "AI-read document needs human review" is not triggered.
- The LLM receives findings and policy text only, never raw document quotes. It cannot add, remove or change findings, and it cannot approve anything. The findings are printed separately from its explanation.
- No FastAPI, storage or audit log here; those stay in the Python app.
