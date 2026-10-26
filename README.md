## Dev Projects

## Standalone GitHub projects discovered in portfolio re-audit

The projects below are in **separate GitHub repositories** (not copies of this monorepo). They should be evaluated on their actual implementation and authorship before being described as customer-delivered or production systems.

| Project | Architectural relevance | Verified scope |
| --- | --- | --- |
| [CaptoGPT / Live Caption RAG Assistant](https://github.com/ydangishere/captogpt) | **Highest priority for RAG portfolio** | Local Markdown section retrieval with lexical ranking → relevant snippets in OpenAI prompt; role-specific knowledge and tests. **No vector database or model training.** |
| [ScrapeNeatly](https://github.com/ydangishere/scrapeneatly) | Browser-based data ingestion + schema-constrained LLM extraction | Playwright HTML acquisition + OpenAI/OpenRouter JSON extraction. No embedding/vector RAG; confirm project authorship and operational tests before CV ownership claims. |
| [AIJobScraper](https://github.com/ydangishere/aijobscraper) | Multi-source data ingestion and AI job filtering | Scraping → LLM filtering → Excel; README references an upstream AIJobScraper repository, so treat as reference/adaptation until original contribution is established. |
| [AI Hotjar 2](https://github.com/ydangishere/aihotjar2) | Conceptual AI-based UI behavior analysis | Reader and simulated click behavior use mock data; **not** a validated GPT-4 Vision or user-analytics implementation. |
| [React Component CI](https://github.com/ydangishere/react-component-ci) | Code testing / CI foundation | React/Jest/GitHub Actions sample; useful supporting engineering evidence but not an AI architecture case study. |

**Verified standalone RAG flow (one horizontal line):** `Windows Live Captions → Question/domain detection → Local Markdown keyword retrieval → Bounded context → GPT → Answer`.

**Portfolio hygiene:** [CaptoGPT Enter](https://github.com/ydangishere/captogpt-enter) is an older related version without the documented knowledge-base architecture; do not double-count it as a distinct RAG system. Forked repositories such as [AutoGPT](https://github.com/ydangishere/AutoGPT) are not evidence of independent authorship. The [AutoGPT YouTube summarizer pull request](https://github.com/Significant-Gravitas/AutoGPT/pull/12987) was closed **without merging**, so describe it as a proposed contribution, not a merged feature.

## Solution Architecture Portfolio (implementation-backed case studies)

The following links show **Solution Architecture Reviews** added to existing project READMEs. Each review distinguishes the implemented flow from architecture decisions, security/performance/cost trade-offs, measurable quality checks and production hardening still required. Architecture documentation is **not evidence of production deployment** or client-delivered outcomes.

| Architecture focus | Project | Evidence and limitation |
| --- | --- | --- |
| Human-governed AI orchestration | [Team Workflow Agent](./team-workflow-agent/README.md#solution-architecture-review-implementation-backed) | Approval gates, specialist advisory prompts, Figma context retrieval, audit records; local-only MVP |
| AI coding-agent enablement | [Website Builder Agent](./website-builder-agent/README.md#solution-architecture-review-implementation-backed) | GPT/Claude concepts, opt-in Codex CLI, nine-stage reviews; no autonomous production publish |
| AI-assisted code review | [Long-run Risk Scanner](./longrun-risk-scanner/README.md#solution-architecture-review-implementation-backed) | Java risk rules, bounded source-context retrieval, optional LLM verification; not vector RAG |
| Real-time model integration | [Voice AI MVP](./voice-ai-mvp/README.md#solution-architecture-review-implementation-backed) | Ephemeral Realtime credential + browser WebRTC; live end-to-end test pending |
| Governed decision-support simulation | [VietPay P2P Lending AI MVP](./vietpay-p2p-lending-ai-mvp/README.md#solution-architecture-review-implementation-backed) | Spring Boot, Kafka, Spark, Ray, LangGraph; mock evidence, no credit decision |
| Stream processing architecture | [VietPay Payment Streaming MVP](./vietpay-payment-streaming-mvp/README.md#solution-architecture-review-implementation-backed) | Transaction outbox → Kafka → Spark → Ray; simulator, not production bank integration |
| Distributed service design | [Microservices](./microservices/README.md#solution-architecture-review-implementation-backed) | Authentication, REST, Kafka, Redis, Elasticsearch, CI workflows |
| Workflow orchestration | [TradingView Airflow MVP](./tradingview-airflow-mvp/README.md#solution-architecture-review-implementation-backed) | Secure webhook and two-alert matching scaffold; AI research/risk/report not implemented |
| Transactional integrity | [Payment Transaction API](./payment-transaction-api/README.md#solution-architecture-review-implementation-backed) | Idempotency-key contract and PostgreSQL transactional workflow |
| SaaS webhook integration | [Stripe Webhook Demo](./stripe-webhook-demo/README.md#solution-architecture-review-implementation-backed) | Signature check, event-ID deduplication, local audit/test flow |

**RAG-style flows (single horizontal line each):**

- **Source-code context retrieval, Long-run Risk Scanner:** `Risk finding → Nearby Java code + symbol references → Bounded context pack → Optional LLM review → Reconciled finding`.
- **Read-only Figma context, Team Workflow Agent:** `Requirements + change log → Optional Figma text fetch → Specialist LLM review → Advisory report → Human approval`.

These are **non-vector retrieval-augmented context patterns**. No dedicated end-to-end vector database RAG system (embeddings → vector search → reranking → grounded answer) is currently implemented in this monorepo. Other projects should not be represented as RAG deployments.

### How to present the work in a solution-architect interview

Explain **the business problem → why this architecture → what code runs today → security and cost trade-offs → how you would validate at production scale**. Use repository source and tests as implementation evidence and clearly label simulations, untested integrations and future designs. The portfolio alone does not verify customer workshops, live production delivery, cloud costs or operational service levels.

This monorepo collects several backend and AI-related projects from the `ydangishere` GitHub account.

### Included sub-projects

- **AI Backend Job Finder** (`aibackendjob_finder`): Desktop app that scrapes TopCV/ITviec job listings and uses an LLM to filter backend positions.  
  - Monorepo folder: [`aibackendjob_finder`](https://github.com/ydangishere/dev-projects/tree/main/aibackendjob_finder)  
  - Original repo: `https://github.com/ydangishere/aibackendjob_finder`

- **Payment Transaction API** (`payment-transaction-api`): FastAPI-based payment/order API with idempotency keys, PostgreSQL, and Redis caching.  
  - Monorepo folder: [`payment-transaction-api`](https://github.com/ydangishere/dev-projects/tree/main/payment-transaction-api)  
  - Original repo: `https://github.com/ydangishere/payment-transaction-api`

- **Microservices** (`microservices`): Node.js/TypeScript microservices system (Auth, People, Case) with PostgreSQL, Redis, Kafka, and Elasticsearch.  
  - Monorepo folder: [`microservices`](https://github.com/ydangishere/dev-projects/tree/main/microservices)  
  - Original repo: `https://github.com/ydangishere/microservices`

- **AI Email Router** (`AIemailrouter`): Python desktop app that classifies emails by intent using an LLM and can send results to Telegram.  
  - Monorepo folder: [`AIemailrouter`](https://github.com/ydangishere/dev-projects/tree/main/AIemailrouter)  
  - Original repo: `https://github.com/ydangishere/AIemailrouter`

- **Case Mini Backend** (`case-mini-backend`): Java/Spring Boot mini case/order backend with CRUD, validation, pagination, and Redis caching.  
  - Monorepo folder: [`case-mini-backend`](https://github.com/ydangishere/dev-projects/tree/main/case-mini-backend)  
  - Original repo: `https://github.com/ydangishere/case-mini-backend`

- **Shopify Speed & Conversion** (`shopify-speed-conversion`): Dawn-based Shopify theme focused on speed optimization and conversion.  
  - Monorepo folder: [`shopify-speed-conversion`](https://github.com/ydangishere/dev-projects/tree/main/shopify-speed-conversion)  
  - Original repo: `https://github.com/ydangishere/shopify-speed-conversion`

- **Shopify Automation** (`shopify-automation`): Node.js service that syncs Shopify orders to Supabase via webhooks.  
  - Monorepo folder: [`shopify-automation`](https://github.com/ydangishere/dev-projects/tree/main/shopify-automation)  
  - Original repo: `https://github.com/ydangishere/shopify-automation`

- **TradingView Alerts to Telegram** (`AIautomationbot`): Python app that opens TradingView, screenshots each alert, and sends them via Telegram.  
  - Monorepo folder: [`AIautomationbot`](https://github.com/ydangishere/dev-projects/tree/main/AIautomationbot)

- **Mini Payment Gateway Simulation** (`nextjs-payment`): Next.js demo of payment flow (create → redirect → callback → verify → update DB) with SQLite, idempotency, and admin token protection.  
  - Monorepo folder: [`nextjs-payment`](https://github.com/ydangishere/dev-projects/tree/main/nextjs-payment)

- **SSO Mini** (`sso`): Spring Boot SSO system. Login once, use many apps. Auth service (IdP) + 2 client apps (app-a, app-b) with JWT.  
  - Monorepo folder: [`sso`](https://github.com/ydangishere/dev-projects/tree/main/sso)

- **AI Video Maker Auto** (`videomakerauto`): Python pipeline to create videos from a topic. GPT → ElevenLabs → MoviePy. Pull, run `run.bat` (Windows) or `run.sh` (Mac/Linux), enter API keys + topic, done. No manual install.  
  - Monorepo folder: [`videomakerauto`](https://github.com/ydangishere/dev-projects/tree/main/videomakerauto)

- **Long-run Risk Scanner** (`longrun-risk-scanner`): Local-first Python CLI + Tkinter GUI for long-term Java/Spring Boot risk patterns (SQLite, optional OpenAI-compatible verify). Run `CHAY_SCAN.bat` / `CHAY_SCAN.sh` or `python app/main.py gui`. Copy `.env.example` → `.env` for API keys (never commit `.env`).  
  - Monorepo folder: [`longrun-risk-scanner`](https://github.com/ydangishere/dev-projects/tree/main/longrun-risk-scanner)

- **Assessment Billing Demo** (`assessment-billing-demo`): Full stack portfolio app with FastAPI backend and Vue 3 + TypeScript SPA for user assessments and billing usage tracking. Includes Docker Compose and pytest API tests.  
  - Monorepo folder: [`assessment-billing-demo`](https://github.com/ydangishere/dev-projects/tree/main/assessment-billing-demo)

- **Stripe Webhook Demo** (`stripe-webhook-demo`): FastAPI microservice for Stripe webhook signature verification, idempotent event processing, and audit logging. Includes Docker Compose, pytest, and Stripe CLI testing guide.  
  - Monorepo folder: [`stripe-webhook-demo`](https://github.com/ydangishere/dev-projects/tree/main/stripe-webhook-demo)

Each subfolder in this repo corresponds to one of the original projects, contains its own `README.md`, and links back to the source repository.

## YouTube AI Agent (Airflow + Telegram)

- **[YouTube Comment AI Agent](youtube-airflow-agent/README.md)** — YouTube Data API v3 → Airflow (00:00 / 12:00, Asia/Ho_Chi_Minh) → SQLite deduplication → optional OpenAI comment analysis → Telegram. Local Docker MVP, no automatic YouTube replies. **[Hướng dẫn tiếng Việt](youtube-airflow-agent/README.vi.md)** | **[English documentation](youtube-airflow-agent/README.en.md)**.
