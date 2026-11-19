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

# Validation update — 2026-11-19

Run on a Windows 11 workstation (Python 3.12, Docker Desktop, NVIDIA RTX 3060 8 GB). Every external service below ran as a local container bound to 127.0.0.1; nothing here is a bank system.

| Check | Result / boundary |
|---|---|
| Unit, API and adversarial tests | 147 passed with every live service configured (`tests/`), Ruff clean. Without the live services, the live tests skip. |
| Neo4j (live, `neo4j:5.26`) | `tests/test_live_services.py`: stored graph returns the same evidence as the local graph, only HMAC tokens are stored, tenants stay in separate scopes, check API reports `backend: neo4j`. Found and fixed a startup crash with `GRAPH_BACKEND=neo4j` (FastAPI no longer has `add_event_handler`). |
| PostgreSQL + pgvector (live, `pgvector/pgvector:pg17`) | Identical metrics and rankings to the in-memory index on all 35 labeled questions; a second retriever reuses stored chunk embeddings (query embedding only); no text column stored; outage falls back without losing rules. |
| ClamAV (live, `clamav/clamav:1.4`) | EICAR detected, clean text passes; upload API rejects infected files (422) and fails closed when the scanner is down (503). |
| OIDC SSO | Mock identity provider over real HTTP (`scripts/mock_idp.py`): valid tokens map to principals; wrong audience/issuer, expired, not-yet-valid, missing exp, forged signature, `none`, HMAC, unknown tenant, no role, two roles and unmapped groups are refused. **Not tested with a bank identity provider.** |
| Encryption at rest | Raw SQLite file contains no application name, document text or check result after a check; rotation re-seals rows and old keys stop working; legacy plaintext rows are encrypted by `scripts/rotate_keys.py`. |
| Qwen (live, Ollama `0.40.15`, `qwen3.5:9b`, 100% GPU) | Extraction and explanation run through the same schema and safety checks as Gemini. Thinking had to be disabled (`reasoning_effort: none`): with it on, a JSON-schema call returned empty content after spending the token budget on reasoning. |
| Qwen vs Gemini comparison | `scripts/compare_models.py` on 16 synthetic rendered scans × 2 formats. Qwen, after two instruction changes found on this same set: 100% field accuracy, 31/32 documents fully correct, 0 injected values accepted, median 5.5 s per document (first run: 79%, 4/32). **Gemini not measured:** free-tier daily quota (HTTP 429) after 2 of 32 calls. Synthetic, not held out; not accuracy on real documents. |
| Transaction investigation | 8 mock scenarios produce the expected money status, confirmed causes and open questions; other-tenant and unknown IDs are indistinguishable; unavailable sources become open questions; unsafe model rephrasing falls back. Mock bank only. |
| Docker image | Built with `INSTALL_VECTOR=true`; container served `/healthz` and an investigation over HTTP. |
| Dependency audit | `pip-audit` on `requirements.txt`, `requirements-vector.txt`, `requirements-graph.txt`: no known vulnerabilities. |

Still not run: a bank identity provider, real bank/MMS APIs, real documents, browser acceptance testing of the new investigation page, and CI on GitHub (runs after push).

```bash
# Live services used above (passwords are local placeholders)
docker run -d --name mms-neo4j -p 127.0.0.1:7687:7687 -e NEO4J_AUTH=neo4j/<password> neo4j:5.26
docker run -d --name mms-pgvector -p 127.0.0.1:5433:5432 -e POSTGRES_PASSWORD=<password> -e POSTGRES_DB=mms pgvector/pgvector:pg17
docker run -d --name mms-clamav -p 127.0.0.1:3310:3310 clamav/clamav:1.4
docker run -d --name mms-ollama --gpus all -e OLLAMA_CONTEXT_LENGTH=16384 -p 127.0.0.1:11434:11434 ollama/ollama:0.40.15
docker exec mms-ollama ollama pull qwen3.5:9b

NEO4J_LIVE_URI=bolt://127.0.0.1:7687 NEO4J_LIVE_PASSWORD=<password> \
PGVECTOR_LIVE_DSN=postgresql://postgres:<password>@127.0.0.1:5433/mms \
CLAMD_LIVE=127.0.0.1:3310 python -m pytest -q
python scripts/compare_models.py
```
