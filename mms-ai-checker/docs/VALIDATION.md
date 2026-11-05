# Validation record — 2026-11-05

## Scope

Independent runnable prototype for synthetic document checking. Local validation is distinct from GitHub Actions, Docker execution, live Gemini evaluation and a bank production rollout.

| Check | Result / boundary |
|---|---|
| Python unit/API/adversarial tests | 38 tests; see `tests/test_checker.py` and final local test output |
| Deterministic regression evaluation | 3/3 synthetic applications match expected finding-code multisets; `evaluation.json` |
| Real Google GenAI SDK with mocked HTTP transport | Tests multimodal payload serialization, JSON response parsing, system instruction and no-tool configuration; **not a live model call** |
| Real HTTP process smoke | Uvicorn startup, health endpoint and authenticated complete demo check exercised over localhost |
| Python lint | Ruff on app/tests/scripts |
| Frontend syntax | `node --check static/app.js`; not equivalent to browser acceptance testing |
| Diagrams | Both generated PNGs inspected for readability and agreement with implemented scope |
| Dependency audit | `pip-audit -r requirements.txt`; initial vulnerable pypdf/python-dotenv pins replaced by patched versions; rerun required whenever dependencies change |
| Docker build / Compose runtime | Configuration supplied; local environment has no Docker executable/daemon, so execution is delegated to configured GitHub CI or the user's Docker host |
| Browser UX acceptance | Not completed locally: remote browser cannot connect to this execution environment's localhost app; access attempt returned client/network errors. API behavior and JS syntax were tested separately. |
| Live Gemini PDF/image quality | **Not run**: no user Gemini key supplied. Adapter contract tests are not evidence of real model accuracy. |
| Real bank/MMS integration and server deployment | **Not run**: no official API contracts, credentials or authorized server supplied |

## Covered test categories

Required/missing documents; expired/today boundary/invalid dates; name mismatch and accent-preserving normalization; extraction failure/low confidence/duplicate field/inconsistent quote; complete demo case without approval; tenant and effective policy gating; rule-preserving retrieval; authentication/roles/object access; mass assignment; malicious questions and document fields; stale document revisions and historical evidence; feedback authorization/audit; file spoofing, encrypted PDF and request size; trusted hosts/CSP; Gemini failure and safe explanation fallback; invalid source page; fabricated finding ID; unsafe explanation links/markup/approval language; production demo-token rejection; actor throttling; Google SDK serialization with mock HTTP.

The corpus is small and synthetic. Passing these tests does not prove resistance to all prompt attacks, malware-safe PDF processing, regulatory compliance, production scale or a particular AI accuracy percentage.

## Repeat

```bash
pip install -r requirements-dev.txt
python -m ruff check app tests scripts
python -m pytest -q
node --check static/app.js
python scripts/evaluate.py
python -m pip_audit -r requirements.txt
```

For HTTP smoke, run the server and `python scripts/smoke.py` in the **same host/network namespace**. It uses the public local-demo checker token. Container CI creates the server, waits for health and exercises the same API.

## Acceptance before a bank pilot

Use approved anonymized held-out documents with human-labeled fields/pages/findings. Run Gemini in an approved data environment, label source correctness and false-clean outcomes, test bad scans/handwriting/Unicode/indirect injection, and measure error rates, p50/p95 latency and token cost. Perform browser acceptance for the employee flow, container/server restore testing, SSO/object authorization tests and independent security review. Record evidence; do not infer these results from mocked tests.

## Tiếng Việt

Đã kiểm tra luồng bằng dữ liệu giả lập, các ranh giới API và một số tình huống thao túng đầu vào. Chưa đo chất lượng Gemini thật, chưa chạy Docker tại môi trường local này và chưa triển khai vào ngân hàng. Số 3/3 chỉ là ba tình huống luật mẫu, không phải “AI chính xác 100%”. Thực hiện lại các lệnh trên và xem kết quả CI thật trước khi tiếp tục thí điểm.
