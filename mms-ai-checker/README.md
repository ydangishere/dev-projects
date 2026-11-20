# VietPay MMS — AI Document Checker

## Workflow diagrams: How MMS AI Checker works

The following two diagrams explain the same six-step document-review process in English and Vietnamese. They are simplified visual guides; detailed architecture and implementation limitations follow below.

### English

![MMS AI Checker: How it works (English)](docs/module_workflow_en.svg)

### Tiếng Việt

![MMS AI Checker: Cơ chế hoạt động (Tiếng Việt)](docs/module_workflow_vi.svg)

**Implementation note:** Demo mode parses sample TXT without invoking an AI model. With `AI_MODE=gemini`, Gemini can extract PDF/image data and explain findings. Final review and approval remain with a bank employee.

---

**MMS website demo:** [View demo](https://ydangkuul.github.io/mms130926/index.html)

> The linked MMS website is a separate UI reference/demo. It is **not** connected to this AI Document Checker backend, and does not imply a production bank integration.


[Tiếng Việt](README.vi.md) · [Security model](docs/SECURITY.md) · [Server deployment](docs/DEPLOYMENT.md) · [Test evidence](docs/VALIDATION.md)

An end-to-end runnable **document-checking assistant for VietPay MMS**, a merchant management system in a payment-company context. Its intended primary users are **PVcomBank Card Center employees**, including the bank's maker and checker roles.

This is an independent portfolio prototype. It is **not an official VietPay/PVcomBank deployment**, has no access to bank systems, and includes only synthetic applications and a synthetic policy. It supports real Gemini calls when configured; default demo mode is deterministic and does not call an AI model.

## Model roadmap: Gemini baseline → Qwen pilot → Fine-tuning

**Selected direction:** compare **Qwen3.5-9B** against **Gemini** during development; evaluate **Qwen + RAG + Graph** in a supervised pilot; fine-tune only after obtaining specialist-reviewed examples and labels. Choose the final production model by validated quality, cost, latency, privacy, and governance requirements — Qwen is not an automatic production commitment.

![Five-stage MMS AI Checker model roadmap](docs/model-roadmap-table.svg)

| Stage | Model | Goal |
| --- | --- | --- |
| **1. Development** | Gemini + Qwen 9B | Compare document extraction and explanations |
| **2. Pilot** | Qwen + RAG + Graph | Collect results, errors and employee feedback |
| **3. Evaluation** | Base Qwen vs Gemini | Measure quality, cost and latency using the same dataset |
| **4. Fine-tuning** | Qwen 9B | Train on reviewed, labeled data |
| **5. Production** | Model meeting acceptance criteria | Deploy only after independent validation and approval |

![Model evolution flow from Qwen and Gemini comparison to supervised production](docs/model-roadmap-flow.svg)

**Target flow:** MMS applications + policies → RAG + Graph Retrieval → compare untuned Qwen3.5-9B with Gemini → review against specialist findings → curate errors and feedback → build training dataset → fine-tune Qwen → evaluate on an independent holdout → supervised pilot and production only after acceptance; otherwise improve retrieval, labels, prompts or the model.

**Stage ordering:** the initial pilot collects data with the base model; a fine-tuned model requires its own independent evaluation and another supervised validation before production. Evaluation is continuous throughout development and pilot, not a one-off step. Keep training and final evaluation datasets separate.

**Technology boundaries:** RAG supplies retrieved context; it **does not train model weights**. Graph Retrieval supports provenance paths between applications, documents, findings and policy rules, while the deterministic Rule Engine retains authority over required checks. Fine-tuning changes model weights only using authorized, privacy-reviewed, specialist-labeled data. Compare finding-level Precision/Recall/F1, extraction accuracy, citation correctness and faithfulness, cost and latency.

**Actual implementation vs roadmap:** The default executable demo parses synthetic TXT and runs the Rule Engine. `AI_MODE=gemini` uses Gemini for PDF/image extraction and explanations; `AI_MODE=qwen` uses Qwen3.5-9B through any OpenAI-compatible endpoint (validated with local Ollama on an 8 GB GPU). Qwen extraction results on synthetic scans are in [`docs/model_comparison.json`](docs/model_comparison.json); the Gemini side of the comparison is pending API quota. Module 1 graph retrieval runs locally or on Neo4j (validated against a live Neo4j 5.26). Policy retrieval is hybrid (vector + BM25), with the vector index in memory or persisted in PostgreSQL + pgvector (validated against a live pgvector 0.8 / PostgreSQL 17). Transaction and payout investigation runs as a LangGraph workflow against a read-only **mock** bank API. **Fine-tuning, connections to real bank systems and a real-data pilot are not implemented.** These images describe the planned model strategy, not completed training.

## One feature within a three-feature assistant

| Assistant capability | Employee asks | Scope of this repository |
|---|---|---|
| **Document checking** | “What is missing for this application to be approved?” | **Implemented:** missing documents, expiry, inconsistent information, unverified versions, uncertainty and evidence |
| Explain transactions and payouts | “Why has this business not received its money?” | **Implemented against a mock bank API:** reads transaction, switch, ledger, risk, reconciliation, payout, merchant and log data, explains status and fees, and separates confirmed causes from open questions |
| Guide handling | “What should I do now?” | **Implemented:** maps each cause or open question to an approved procedure (`policies/transaction_procedures.yaml`) with steps, escalation team and the MMS screen to open; marks steps the caller's role cannot perform |

None of the three features approves, rejects, changes KYC/KYB status, requests documents externally, retries, reverses or moves money. The employee decides and acts in existing bank workflows.

## Transaction and payout investigation (implemented with a mock bank)

**Status: implemented in [`app/investigation.py`](app/investigation.py) as a LangGraph workflow, against a synthetic read-only mock bank API ([`app/mock_bank.py`](app/mock_bank.py), data in [`samples/bank_mock.json`](samples/bank_mock.json)).** Open **http://127.0.0.1:8000/investigate** (link in the checker header) or call `POST /api/investigations` with `{"transaction_id": "TXN-1001"}`. Sample IDs `TXN-1001` to `TXN-1008` cover paid with fees, issuer decline, settlement not yet due, risk hold, payout to a closed account, merchant blocked by pending KYC (linked back to the AI Check application) with a fee mismatch, customer debited but switch timeout (left unresolved), and refund. `BANK_MODE=http` with `BANK_API_URL`/`BANK_API_TOKEN` points the same adapter at a real bank API with the same read-only contract; production refuses the mock. Any role can investigate; results are stored encrypted when a key is set, tenant-scoped and audited. The employee's question is recorded but cannot change which data is read, the diagnosis or the steps.

```mermaid
flowchart TD
    A[Employee enters Transaction ID] --> B[FastAPI authentication and role / tenant authorization]
    B --> C[LangGraph workflow: fetch transaction → gather evidence → diagnose → plan guidance → explain]
    C --> D[Read-only bank adapter: mock API now, bank API via BANK_MODE=http]
    D --> E1[Authentication API - historical auth evidence]
    D --> E2[Transaction API - status and error codes]
    D --> E3[Core Banking API - debit and ledger entries]
    D --> E4[Payment Switch API - routing and bank response]
    D --> E5[Fraud / Risk API - holds and risk decisions]
    D --> E6[Transaction Logs - timestamps and correlation IDs]
    D --> E7[Reconciliation API - settlement and matching status]
    E1 --> F[Aggregate evidence and identify unknowns]
    E2 --> F
    E3 --> F
    E4 --> F
    E5 --> F
    E6 --> F
    E7 --> F
    F --> G[RAG - approved error-code catalog, policies and handling procedures]
    G --> H[LLM - grounded explanation and recommended next steps]
    H --> I[Employee reviews result; no autonomous fund movement]
```

**Data versus knowledge:** Transaction, core-banking, switch, fraud, log and reconciliation APIs provide **transaction-specific evidence**; the procedure catalog provides **approved knowledge** to interpret error codes and list handling steps. The catalog is never the source of transaction status, debit/credit confirmation or reconciliation truth. Causes are looked up by code rather than by free-text search, so a question cannot pull in an unrelated procedure. The diagnosis is deterministic; with `AI_MODE=gemini` or `qwen` a model may rephrase the answer from cause codes, statuses, amounts and dates only (no names or account numbers), and its output must name exactly the same causes and pass safety checks, otherwise the deterministic text is shown.

**Investigation rules:** Enforce authorization before any lookup; use read-only, least-privilege adapters and redact sensitive data; correlate timestamps and IDs across services. Keep `FAILED`, `PENDING` and confirmed `SUCCESS` distinct. A debit followed by a payment-switch timeout does **not** prove that the recipient was not credited: treat it as unresolved until receiving-bank confirmation/reconciliation, and never automatically retry or reverse money movement. Surface verified facts separately from unresolved questions, record audit traces and route financial actions to existing controlled bank workflows.

**The mock API mirrors these data sources so the workflow can be built and tested; it is not a claim that the bank exposes the same endpoints.** Authentication history is not used by the current diagnosis. Real availability and semantics depend on the bank and payment rail.

## Quick start

Python **3.12** and a modern browser are sufficient. Start from the monorepo root:

```bash
cd mms-ai-checker
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m uvicorn app.main:app --env-file .env --host 127.0.0.1 --port 8000 --no-access-log
```

On Windows PowerShell, replace activation and copy with:

```powershell
cd mms-ai-checker
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --env-file .env --host 127.0.0.1 --port 8000 --no-access-log
```

Open **http://127.0.0.1:8000**, enter `demo-checker-token`, connect, select an application and click **Kiểm tra hồ sơ**. Open **Xem căn cứ** for a finding, inspect the source and policy, then submit a correct/incorrect/needs-review assessment. Logout removes the token from page memory.

| Sample | Expected behavior |
|---|---|
| `APP-DEMO-001` | Missing bank confirmation, expired ID, license v2 not verified |
| `APP-DEMO-002` | Bank-confirmation name differs; human review, not a fraud finding |
| `APP-DEMO-003` | No issue found within demo rules; **not approval eligibility** |

Demo tokens: `demo-maker-token` can upload/check; `demo-checker-token` also submits feedback; `demo-viewer-token` only reads. These are deliberately public local-demo credentials. For a TXT replacement, create a UTF-8 file containing e.g. `expires_on: 2030-12-31`. Uploading always creates a pending version; the service cannot mark it verified.

### Enable real Gemini PDF/image reading

Edit local `.env` (never commit it):

```dotenv
AI_MODE=gemini
GEMINI_MODEL=gemini-3.8-flash
GEMINI_API_KEY=YOUR_OWN_KEY
```

Restart the server, open an application and upload synthetic PDF/JPEG/PNG documents into the appropriate document slots. Maximum **5 MiB per file, 20 PDF pages, 20 million image pixels**. Replace all TXT sample slots if you want to exercise an entirely PDF/image-based application. Uploads remain pending upstream verification.

The implementation uses the Google GenAI SDK `models.generate_content`, multimodal document input and JSON Schema output. Gemini supplies field values, page, quote and confidence; it does not set verification or approval. OCR here means the document-reading stage using Gemini's native vision; a separate OCR vendor is not required. Failed or unknown extraction becomes a review finding. No API key is shipped; live Gemini validation requires your key and account access.

**Runnable models:** `gemini-3.8-flash` (`AI_MODE=gemini`) and Qwen3.5-9B (`AI_MODE=qwen`, `QWEN_MODEL=qwen3.5:9b` on Ollama, or any OpenAI-compatible server such as vLLM or a hosted endpoint via `QWEN_BASE_URL`/`QWEN_API_KEY`). Both use the same system instructions, strict JSON schema, Pydantic validation and explanation safety checks; Qwen receives PDFs as their text layer per page, or the embedded page image for scanned PDFs. Qwen3.5 thinks by default, which can use the whole output budget under a JSON schema, so `QWEN_REASONING_EFFORT=none` turns thinking off. [Official model documentation](https://aistudio.google.com/docs/models/gemini-3.8-flash), [document input](https://aistudio.google.com/docs/document-processing), [structured output](https://aistudio.google.com/docs/structured-output), checked 2026-11-05.

### Qwen vs Gemini comparison (synthetic; Gemini pending)

`python scripts/compare_models.py` renders the 16 synthetic documents in [`samples/extraction_eval.json`](samples/extraction_eval.json) (Vietnamese business licences, ID cards and bank confirmations with distractor names and numbers, absent fields and embedded instructions) to a PNG scan and an image-only PDF, then asks each model to extract the facts. Both models read pixels, never the ground-truth text. It also generates explanations for the demo applications. Qwen3.5-9B on a local RTX 3060 8 GB, single run at temperature 0. **Gemini was not measured:** the free-tier key hit its daily request quota (HTTP 429) after 2 of 32 calls; rerun `python scripts/compare_models.py --models gemini` with a billing-enabled key or after the quota resets.

| Measure | qwen (`qwen3.5:9b`) |
|---|---|
| Field accuracy (all scans) | 100% |
| Field accuracy, PNG / image-only PDF | 100% / 100% |
| Documents fully correct | 31 / 32 |
| Unsupported facts (value for a field the document lacks) | 1 |
| Injected values accepted | 0 |
| Schema or call failures | 0 |
| Quote found in source text | 77% |
| Median / p90 seconds per document | 5.5 / 8.6 |
| Explanations passing safety validation | 2 / 2 |

Qwen needed two changes, which now apply to both models: precise field definitions in the extraction instruction, and the server telling the model which fields the rules use for the document kind (other fields are dropped server-side). Field accuracy went from 79% to 92% to 100%, and unsupported facts from 38 to 32 to 1. The instruction was revised after looking at this same set, so the last number is not a held-out score. No run accepted an injected value. These are 16 author-written synthetic documents, so the table shows that the Qwen path works end to end and where it fails, not accuracy on real bank documents. Latency depends on hardware and network. Per-document results are in [`docs/model_comparison.json`](docs/model_comparison.json). Choosing a production model still needs authorized, labeled real documents and the cost and data-handling review in the roadmap above.

## Backend flow

![Backend flow: authentication, OCR, RAG, rules, Gemini explanation, evidence and employee review](docs/backend_flow.png)

**OCR reads documents → RAG finds policy → Rule Engine checks → Gemini explains.**

1. FastAPI authenticates a server-configured principal and checks tenant/role. It reads application metadata and current source bytes from the repository adapter, currently SQLite fixtures/uploads.
2. Demo mode parses known TXT fields. Gemini mode reads actual PDF/images into strict Pydantic JSON: `field`, `value`, `page`, `quote`, `confidence`. Unknown values are omitted and treated as uncertainty.
3. RAG loads the versioned local Markdown policy, splits it into section-aware chunks with source metadata, filters chunks by tenant, effective date and policy version, then runs hybrid retrieval: question decomposition and rewriting, vector search plus BM25 keyword search, Reciprocal Rank Fusion and reranking (see AI Check RAG design below). Every rule used by the checker is always included. The question can reorder policy sections but cannot suppress a rule or substitute a policy file; a suspicious question is ignored for retrieval.
4. The Python Rule Engine executes synthetic `rules.yaml`: required document types, expiry, normalized names/registration numbers, current verification version and minimum extraction confidence. Rules determine findings; the LLM cannot remove them.
5. Gemini receives immutable findings and retrieved policy sections for explanation, without raw document quotes, names or registration IDs in this second call. Strict JSON, known finding IDs and output screening are enforced. Invalid/model-failed explanations fall back to deterministic text. Extracting documents still sends their original content to Google when Gemini mode is selected.
6. SQLite stores the application snapshot, source bytes/versions/hashes, extracted JSON, findings, exact retrieved policy sections/hash and audit events. Evidence comes from this historical snapshot. Replacing a document makes old results stale and blocks feedback until a new check.

Hard findings and AI explanation are displayed separately. Gemini quotes are **model-proposed evidence**, not guaranteed ground truth: page bounds and value/quote consistency are checked, but employees must inspect the actual source. Every document read by a model (Gemini or Qwen) receives an explicit human-review finding.

### Module 1 graph retrieval — implemented locally, optional Neo4j

This diagram shows the hybrid architecture. **Implemented for Module 1:** application → required document / uploaded document → Rule Engine finding → policy rule relationships, graph traversal with a local deterministic backend or a persisted Neo4j graph (validated live), graph-assisted deterministic rule prioritization, and graph evidence included with check results and model explanations. Policy retrieval uses the hybrid retriever in `app/retrieval.py`; the vector index is in memory by default or in PostgreSQL + pgvector (`VECTOR_STORE=pgvector`). **Not implemented:** a model-based (cross-encoder) reranker.

```mermaid
flowchart TB
    Q["User Query<br/>Bank employee asks a question"] --> P["Query Processing"]
    P --> V["Vector Retrieval (live)<br/>In-memory or PostgreSQL + pgvector<br/>Find policy chunks"]
    P --> G["Graph Retrieval (Module 1 live)<br/>Local / optional Neo4j<br/>Application, document, finding, policy relationships"]
    V --> M["Merge + Reranking"]
    G --> M
    M --> L["LLM (OpenAI / Gemini)"]
    L --> A["Answer + Evidence + Citations"]
```

**How the branches differ:** The vector index stores embeddings of approved document chunks and finds semantically relevant policies. The Module 1 graph stores server-authorized application, document, finding and rule relationships. Customer-account and transaction graphs belong to a future module and are not implemented. Creating graph nodes is **not** the same thing as converting embeddings into nodes, and a graph can optionally retain embeddings too. Ingestion/chunking and extraction of approved entities and relations happen before query-time retrieval.

**Banking safety:** Authenticate and enforce tenant/role/object permissions before either retrieval path. Graph records must come from approved policy data or authorized, read-only business systems; graph links by themselves do not prove why an application was rejected or whether a payment settled. Merge only traceable evidence, preserve mandatory Rule Engine findings, identify missing evidence, and require employee review. Neo4j persistence is optional. The local graph branch is on by default. The graph links already-computed findings and does not independently validate KYC, accounts, or banking transactions.

### Run and inspect Module 1 Graph Retrieval

The default `GRAPH_BACKEND=local` requires no external database. Start the existing FastAPI app, run a document check, and inspect `graph_retrieval.backend` and `graph_retrieval.evidence` in the `POST /api/applications/{id}/checks` response. Each `GET /api/checks/{id}/evidence/{finding_id}` also includes a `graph` field. Graph reranking never removes the policy sections required by the Rule Engine.

To persist and query graph edges in **Neo4j**, run:

```bash
pip install -r requirements-graph.txt
# Set GRAPH_BACKEND=neo4j, NEO4J_URI, NEO4J_USERNAME,
# NEO4J_PASSWORD, GRAPH_HMAC_KEY (32+ secret characters) in .env
python -m uvicorn app.main:app --env-file .env --host 127.0.0.1 --port 8000
```

Alternatively, configure the Neo4j password and HMAC key in `.env` then use `docker compose -f compose.yaml -f compose.graph.yaml up --build` to run the optional Neo4j stack. The normal `docker compose up` still starts only the checker with its local graph. Neo4j nodes use HMAC-pseudonymized keys; no raw names, registration numbers, document bytes, or prompts are sent to the graph database. On Neo4j query failure, the graph falls back to local evidence, logs `neo4j_unavailable_local_fallback`, and leaves deterministic findings unchanged. **Validated against a live Neo4j 5.26 container:** `tests/test_live_services.py` checks that the stored graph returns the same evidence as the local graph, stores only pseudonymous tokens, keeps tenants in separate scopes and works through the check API (`NEO4J_LIVE_URI=bolt://127.0.0.1:7687 NEO4J_LIVE_PASSWORD=... pytest tests/test_live_services.py`). The live test found and fixed a startup crash with `GRAPH_BACKEND=neo4j` on the current FastAPI version.

## AI Check RAG design

We have selected the following approach to build RAG (retrieval-augmented generation) for the AI Check / document-checking module. It retrieves applicable policy evidence to explain document-checking findings; it is separate from the transaction-investigation module.

**Status: implemented (phase 1) in [`app/retrieval.py`](app/retrieval.py).** Every check now runs decomposition → rewriting (Vietnamese/English domain terms, with or without accents) → metadata filtering (tenant, effective date and policy version from server data) → hybrid search (vector + BM25 keyword, merged with Reciprocal Rank Fusion and deduplicated by chunk ID) → reranking (fused score plus query-term coverage) → rule-level policy sections. Each check result includes a `policy_retrieval` trace with subqueries, rewritten queries, filters, embedder and ranked candidate chunks.

- **Embeddings:** `EMBED_MODE=local` (default) uses deterministic hashed word and character n-gram vectors. It runs offline with no model download, but it matches spelling overlap rather than meaning. `EMBED_MODE=fastembed` uses an offline multilingual semantic model (`LOCAL_EMBED_MODEL`, default `paraphrase-multilingual-MiniLM-L12-v2`, installed with `requirements-semantic.txt`); text never leaves the server. `EMBED_MODE=gemini` uses the Gemini embedding API (`GEMINI_EMBED_MODEL`) and sends policy text and the employee question to Gemini; it has been run against the live API on the synthetic question set (`gemini-embedding-001`). If embedding fails, the check falls back to local embeddings and records an event.
- **Measured limitation:** the labeled questions are split into `dev` (used while building the retriever) and `holdout` (different wording, never used for tuning). With local hashed embeddings, hybrid retrieval beats the lexical baseline on dev, but on holdout it does not beat it on MRR or NDCG: the rewrite vocabulary fits the dev wording. The offline semantic model (`fastembed`) and Gemini embeddings (`gemini-embedding-001`) both score higher than the lexical baseline on holdout, Gemini the highest of the three. See `docs/evaluation.json`; these are small author-written fixtures, not a production benchmark.
- **Persistent vector index:** `VECTOR_STORE=pgvector` with `PGVECTOR_DSN` (install `requirements-vector.txt`) stores chunk embeddings in PostgreSQL + pgvector, so they survive restarts, are shared by several instances, and paid embedding calls are made once per policy version and chunk setting. Only the index namespace, chunk ID, rule ID, tenant, policy version and vector are stored, not policy text or questions. Search is exact cosine distance restricted to chunks that passed metadata filtering, with a tenant condition in SQL. If the database is down, retrieval falls back to in-memory local embeddings and records `vector_index_unavailable_local_fallback`. Validated live: identical rankings to the in-memory index on all 35 labeled questions. Supabase is PostgreSQL with pgvector, so the same DSN works there; a self-hosted container was used here. The untyped `vector` column allows different embedders; add an HNSW index per fixed dimension when the corpus grows.
- **Not yet implemented:** a model-based reranker and LLM-based query rewriting. Rewriting uses a fixed domain vocabulary list.
- **Settings:** chunk size, overlap, candidate Top-K and fusion constants live in `RetrievalSettings`. They are experiment settings, not tuned optima.

### 1. Prepare documents when they are added or updated

```text
Upload --> Parse content and structure --> Split into chunks --> Attach source references and metadata --> Generate embeddings --> Build vector and keyword indexes
```

This is the document-preparation flow, not work to repeat for every question. Preserve document/page/section references, policy version and effective dates for each chunk. When policy content changes, refresh affected chunks and indexes; retain historical evidence and exclude superseded versions from current-policy retrieval. Chunk size and overlap are configurable experiment settings, not proven optimal values.

### 2. Retrieve and answer each question

```text
Query --> Query Decomposition (if needed) --> Query Rewriting --> Metadata Filtering --> Hybrid Search [Vector Search + Keyword Search --> Merge results and remove duplicates] --> Reranking --> Select chunks --> Generation
```

1. Query: receive the employee's question with the selected application's authorized context. Authentication and application access checks remain a prerequisite, before this flow.
2. Query Decomposition: split a multi-part question into smaller questions when necessary. Simple questions pass through unchanged.
3. Query Rewriting: clarify each question using available conversation/application context. Preserve intent, identifiers and conditions; ask for clarification when context is insufficient.
4. Metadata Filtering: after rewriting, restrict retrieval to the server-authorized tenant, applicable document type, approved policy version and effective date. Rewriting cannot change or relax permissions.
5. Hybrid Search: run vector search over chunk embeddings for meaning and keyword search for exact terms/codes within the filtered scope; merge results and remove duplicates. Query and document embeddings must use compatible models; cosine similarity is one possible vector-scoring method.
6. Reranking: score the retrieved candidates against each clarified question, then select the most useful chunks. Candidate count (Top-K) and final context count are separate settings; combine evidence from the subquestions when needed.
7. Generation: use the original question, selected policy chunks and immutable Rule Engine findings to produce an explanation with source references. Required rule evidence must remain included even if it falls outside the ranked shortlist. The model cannot remove findings or approve a dossier; insufficient evidence must be reported as uncertainty.

### Chunking Lab and experiment history (implemented)

The Chunking Lab is available at `/lab` (link in the checker header). A maker or checker can change chunk size, overlap, candidate Top-K, fusion constant, coverage weight and embedding backend, preview the resulting chunks, run the labeled question set (dev, holdout or all) and compare the lexical baseline with hybrid retrieval. Each run is stored in SQLite with its configuration, embedder, dataset and policy hashes, per-question rankings, top chunks, scores, processing time, run date and actor, and listed newest first. APIs: `GET /api/lab/chunks`, `POST /api/lab/experiments`, `GET /api/lab/experiments[/{id}]`. The guidance below still applies.

For each experiment, record the configuration, document/dataset versions, chunking strategy and parameters, embedding model and index version, retrieval/reranking settings, labeled question set, retrieved chunks and their ranking, generated answers, evaluation scores, processing time and run date.

Change one parameter or strategy at a time, rerun the same test questions and compare the saved results. When comparing chunking strategies, keep the documents, labeled questions, embedding model and retrieval configuration fixed so that the effect of chunking can be assessed. Historical experiments must retain their configuration and evidence for reproducible comparisons.

For evaluation of this planned pipeline, use the same labeled questions and applicable policy versions when comparing configurations. Recall@K and Precision@K measure retrieval coverage and relevance; MRR (Mean Reciprocal Rank) and NDCG (Normalized Discounted Cumulative Gain) measure ranking quality. Evaluate answer faithfulness and answer correctness separately. These are evaluation results, not ranking knobs, and are not claimed as measured by the current three-case synthetic checker evaluation.

### Evaluation and observability tools (optional, implemented)

These tools have different roles and are all optional; the app, tests and CI run without them. ranx: `requirements-eval.txt`, used by `scripts/evaluate.py`. Ragas: `requirements-eval.txt`, used by `scripts/evaluate_answers.py` with `OPENAI_API_KEY`. LangSmith: `requirements-observability.txt` plus `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY`; traces send only the question, tenant, review date, rule IDs, scores and chunk IDs, never policy text, application data or documents.

| Tool | Role in the AI Check RAG / Chunking Lab design |
|---|---|
| [LangSmith](https://docs.langchain.com/langsmith/evaluation-types) | Trace pipeline steps, manage evaluation datasets and compare experiments through its interface. Record retrieved context, answers, timing and evaluator feedback to investigate regressions. |
| [Ragas](https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/) | Evaluate generated answers, including faithfulness to retrieved evidence and factual correctness against reference answers. Supply the question, retrieved context, generated answer and reference data required by each chosen metric; some evaluators use a separate judge model. |
| [ranx](https://amenra.github.io/ranx/metrics/) | Compute retrieval/ranking metrics: Recall@K, Precision@K, MRR (Mean Reciprocal Rank) and NDCG (Normalized Discounted Cumulative Gain), from ranked chunk IDs/scores and labeled relevance judgments. |

Planned evaluation flow:

```text
Run a labeled question set --> Collect retrieved chunks and generated answers --> ranx scores retrieval/ranking + Ragas evaluates answers --> Store scores with experiment configuration --> Compare in Chunking Lab and optionally LangSmith
```

Chunking Lab is the custom workspace for selecting chunking strategies, changing parameters and previewing chunks. It can display results produced by these tools; it is not a replacement name for any of them. LangSmith provides an additional experiment/tracing interface, while ranx and Ragas can run in the Python backend.

Keep the metric names and definitions explicit: Ragas context metrics are not automatically identical to standard ID-based Recall@K or Precision@K. Validate answer-judge scores with human review. `python scripts/evaluate.py` scores the lexical baseline and hybrid retrieval on the dev and holdout splits of [`samples/retrieval_questions.json`](samples/retrieval_questions.json) (Recall@3, Precision@3, MRR, NDCG@5), includes the offline semantic model when installed, and cross-checks with ranx when installed; CI fails if hybrid scores below the lexical baseline on dev. `python scripts/evaluate_answers.py` generates a short answer from the retrieved policy sections and scores it with Ragas faithfulness, factual correctness (against the reference answer) and context recall, writing [`docs/answer_evaluation.json`](docs/answer_evaluation.json). Answer generation and judging there use OpenAI models, not the Gemini path used by the checker; the scores are LLM-judge estimates on synthetic data.

### What MD, YAML and JSON do

| Format | Used for |
|---|---|
| Markdown | Versioned human-readable policy sections for retrieval |
| YAML | Controlled machine-readable thresholds and required documents |
| JSON | Sample applications, typed extracted facts, API requests/results and evaluation output |
| Original PDF/image/TXT | Historical evidence; preserved rather than replaced by extracted text |

Markdown/YAML/JSON are storage formats. They do not, by themselves, implement RAG or an AI agent. The retrieval and orchestration code makes them part of the workflow.

## Employee UX flow

![Employee UX: select application, ask, review findings, inspect sources, correct and rerun, give feedback, decide in MMS](docs/ux_flow.png)

Example conversation: employee asks **“Hồ sơ này còn thiếu gì để được duyệt?”** The assistant identifies missing bank confirmation, an expired ID and an unverified license version, each linked to a policy section and source. The employee inspects originals, asks for correction through the existing bank workflow and runs a new check after upload. Feedback is persisted for review; it never automatically retrains the model or changes an approval.

The conversation is deliberately bounded to checking the selected application. Arbitrary questions are not executed as tools or policy instructions. No autonomous multi-agent system or general banking chatbot is claimed.

## REST APIs

All `/api/*` endpoints require `Authorization: Bearer <token>`. Identity, tenant and role come only from server configuration. There are **8 business endpoint patterns** plus health and OpenAPI metadata; these are endpoints of one service, not eight microservices.

| Method / path | Purpose | Allowed role |
|---|---|---|
| `GET /api/applications` | List authorized applications | Viewer, maker, checker |
| `GET /api/applications/{id}` | Metadata and current document manifest | Viewer, maker, checker |
| `POST /api/applications/{id}/documents` | Bounded multipart upload; new pending version | Maker, checker |
| `POST /api/applications/{id}/checks` | Synchronous completed check; JSON `{ "question": "..." }` | Maker, checker |
| `GET /api/checks/{id}` | Historical result plus current stale flag | Viewer, maker, checker |
| `GET /api/checks/{id}/evidence/{finding_id}` | Exact finding, source metadata and policy section | Viewer, maker, checker |
| `GET /api/checks/{id}/documents/{document_id}` | Authorized original source download | Viewer, maker, checker |
| `POST /api/checks/{id}/feedback` | Record reviewer assessment | Checker |
| `GET /healthz` | Process/storage readiness and mode; not live-model health | Public |
| `GET /openapi.json` | Machine-readable REST contract | Public |

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/applications/APP-DEMO-001/checks \
  -H 'Authorization: Bearer demo-checker-token' \
  -H 'Content-Type: application/json' -d '{"question":"Hồ sơ này còn thiếu gì?"}'
```

Important responses: `401` no identity, `403` wrong role, `404` unknown/other-tenant object, `409` unavailable policy or stale feedback, `413` request too large, `422` invalid data/file, `429` rate/capacity limit, `503` unconfigured Gemini. A check can complete with `extraction_failed` findings when a document call fails; inspect `events`, not only HTTP status.

### External integrations and banking terminology

Implemented external integrations: the **Gemini API**, any **OpenAI-compatible Qwen endpoint**, **OpenID Connect SSO** (validates signed access tokens from the bank identity provider; tested with a local mock provider in `scripts/mock_idp.py`, not with a bank IdP), **ClamAV** (clamd), **Neo4j**, **PostgreSQL + pgvector**, and the **bank data API contract** for investigations (exercised against the mock bank). MMS application API, document storage, KYC/KYB and real bank account/customer/transaction APIs are **integration seams, not connected systems**. Local SQLite fulfills the application/document repository role in this build.

No issuer/acquirer transaction messaging, ISO 8583, payment authorization, clearing or settlement is performed. The investigation module only **reads** status, settlement and payout data and explains it. No real banking credentials or customer data belong in this public repository.

## End-to-end engineering ownership

| Stage | What this build supplies | What production still needs |
|---|---|---|
| Define problem | Document-checking scope, employee UX, issue taxonomy and advisory boundary | Card Center stakeholder validation and approved success criteria |
| Prepare data | Three synthetic visible cases plus hidden-tenant fixture | Authorized anonymized sample set and domain-expert labels |
| Prepare policy | Synthetic Markdown/YAML, effective date, version and SHA-256 | Official approved policy owner, change review and release procedure |
| Build AI pipeline | Gemini adapter, typed extraction, hybrid policy RAG (local vector + keyword), deterministic rules, explanations/fallback | Live Vietnamese document benchmark and chosen data-processing arrangement |
| Build product/backend | Python/FastAPI, REST, web UI, SQLite snapshots and feedback, transaction investigation workflow, OIDC SSO adapter | Real MMS/storage/bank API adapters, production database if scale requires |
| Test/security | Unit/API/adversarial tests, synthetic regression evaluation, dependency audit CI | Bank penetration test, broader attack corpus, independent review |
| Package/deploy | Dockerfile, hardened local Compose, optional service stack (`compose.services.yaml`: ClamAV, pgvector, Ollama), health endpoint and deployment runbook | Authorized server, TLS, secret manager, bank IdP registration, backups, operational rollout |
| Operate/improve | Audit events, reviewer feedback, Prometheus `/metrics` (requests, latency, checks, findings, rejected uploads, investigations) | Central collector, alerts, cost/token dashboards, SLO and incident ownership |

## Docker and CI/CD

```bash
cp .env.example .env
docker compose up --build -d
docker compose logs -f checker
```

Open the same localhost URL. Docker packages one **modular monolith**. It runs as a non-root user with a read-only root filesystem, dropped capabilities, no-new-privileges, resource limits and a persistent `/data` volume. It is deployment isolation, not a complete hostile-file sandbox. No microservices, Kafka, gRPC or Kubernetes are necessary for this MVP. Checks run synchronously, two at a time, one process; larger workloads need durable jobs, distributed throttling and tested storage/queue capacity.

CI lives at [`../.github/workflows/mms-ai-checker.yml`](../.github/workflows/mms-ai-checker.yml): lint → tests → synthetic evaluation → dependency vulnerability audit → Docker build → HTTP container smoke test → evaluation artifact. Tests do not need Gemini secrets. CI is configured; verify actual run results in GitHub Actions after push. **CD is an operator deployment runbook**, not an automatic deployment to a bank server. See [deployment and rollback](docs/DEPLOYMENT.md).

## Security and limits

Implemented defenses include object-level tenant authorization, role checks, server-owned document versions, strict JSON fields, file/type/size/page limits, parameterized SQL, output escaping/CSP, model input separation, no model tools, immutable findings, source/version snapshots, bounded model calls, concurrency/actor limits and audited feedback.

Indirect prompt injection, “reverse approach” prompts (e.g. asking what *not* to do in order to extract bypass instructions), hidden/Unicode instructions, field manipulation, forged roles/verification, fabricated citations and model output abuse are covered by boundaries and selected adversarial tests. Keyword screening is only supplemental; no system can claim complete protection from every prompt attack. Read the [implemented control / residual risk matrix](docs/SECURITY.md).

**Security controls added for a pilot:**

- **SSO:** `AUTH_MODE=oidc` validates bank-issued JWT access tokens against the provider's JWKS: asymmetric algorithms only (no `none` or HMAC), issuer, audience, expiry, not-before, subject. Tenant must be in `OIDC_ALLOWED_TENANTS`; groups map to exactly one role through `OIDC_ROLE_MAP`, and a user mapped to both maker and checker is refused. An unreachable provider returns 503. Tested against a local mock provider, not yet a bank IdP.
- **Encryption at rest:** with `DATA_ENCRYPTION_KEY`, application bodies, document bytes, check results, evidence copies and investigations are sealed with AES-256-GCM; row ID and column are bound as associated data so a value copied to another row fails. `scripts/rotate_keys.py` encrypts old plaintext rows or rotates keys (`DATA_ENCRYPTION_OLD_KEYS`) and vacuums the file. IDs, tenant, document kind and audit rows stay plaintext for queries. Protect the key in a secret manager; disk/backup encryption is still recommended.
- **Malware scanning:** `MALWARE_SCAN=clamd` streams every upload to ClamAV before it is stored; infected files are rejected (422) and audited with the signature, and an unreachable scanner rejects the upload (503). Validated against a live ClamAV 1.4 container with the EICAR test file. Signatures only catch known malware; parsing is still not isolated in a separate sandbox.
- **Metrics:** `/metrics` in Prometheus text format, off unless `METRICS_TOKEN` is set. Labels are route templates, status codes, modes and finding codes only; no tenant, user, application ID or content.
- **Production gate:** `APP_ENV=production` refuses to start without an encryption key, `MALWARE_SCAN=clamd`, strong tokens or OIDC, and a real bank API (`BANK_MODE=http`).

Still missing before an authorized pilot: a bank IdP registration and role mapping review, isolated file parsing, signed policy publishing, a central telemetry backend, real bank API contracts and a benchmark on real authorized documents.

## Tests and reproducible evaluation

```bash
pip install -r requirements-dev.txt
python -m ruff check app tests scripts
python -m pytest -q
python scripts/evaluate.py
python -m pip_audit -r requirements.txt
# With the server running:
python scripts/smoke.py
# Optional, against live services (tests skip when unset); see docs/VALIDATION.md:
NEO4J_LIVE_URI=bolt://127.0.0.1:7687 NEO4J_LIVE_PASSWORD=... \
PGVECTOR_LIVE_DSN=postgresql://postgres:...@127.0.0.1:5433/mms CLAMD_LIVE=127.0.0.1:3310 \
python -m pytest -q tests/test_live_services.py tests/test_security_controls.py
# Qwen vs Gemini on synthetic scans (needs Ollama/Qwen and GEMINI_API_KEY):
python scripts/compare_models.py
```

The full optional stack (ClamAV, pgvector, Ollama) starts with `docker compose -f compose.yaml -f compose.services.yaml up --build`; set `PG_PASSWORD` in `.env` first.

[`docs/evaluation.json`](docs/evaluation.json) reports exact finding-code matches on **three synthetic deterministic cases**, not production accuracy or Gemini OCR quality. It also includes a `policy_retrieval` comparison of the lexical baseline and hybrid retrieval on labeled synthetic questions; these are small author-written fixtures, not a production retrieval benchmark. See [validation record](docs/VALIDATION.md) for what was actually run and what remains unverified.

For a genuine model benchmark, label field values, source pages and expected findings on held-out authorized documents. Measure missing/expired/mismatch precision/recall, unsupported-source rate, false-clean outcomes, manual-review rate, p50/p95 latency and cost per application. Never invent a “92% accuracy” or time-saving claim from these fixtures.

Code layout: `app/main.py` REST/auth/orchestration, Chunking Lab and investigation API; `providers.py` Gemini/Qwen/demo; `auth.py` OIDC; `crypto.py` encryption at rest; `scanning.py` ClamAV; `metrics.py` Prometheus metrics; `investigation.py` LangGraph transaction workflow; `mock_bank.py` synthetic bank API; `rag.py` policy loading and legacy lexical ranking; `retrieval.py` hybrid retrieval and embedders; `vectorstore.py` memory/pgvector index; `retrieval_eval.py` retrieval metrics; `observability.py` optional LangSmith tracing; `engine.py` rules; `graph.py` graph retrieval; `store.py` SQLite; `static/` employee UI, investigation page and Chunking Lab; `policies/` MD/YAML; `samples/` JSON; `tests/` (live service tests skip unless configured); `scripts/`; `docs/`. Diagram sources can be regenerated with `python scripts/diagrams.py` (Pillow and DejaVu Sans on Linux).
