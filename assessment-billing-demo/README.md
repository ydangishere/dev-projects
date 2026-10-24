# Assessment Billing Demo

Part of the [`dev-projects`](https://github.com/ydangishere/dev-projects) monorepo.

Portfolio demo for **FastAPI + Vue.js + TypeScript** full stack development.

## Features

- FastAPI REST API for user assessments (CRUD)
- Billing usage endpoint with plan limit checks
- Vue 3 + TypeScript SPA (form, table, billing panel)
- Docker Compose for local full-stack run
- Pytest API tests

## Stack

- Backend: Python, FastAPI, SQLAlchemy, SQLite
- Frontend: Vue 3, TypeScript, Vite
- DevOps: Docker, Docker Compose

## Quick start (Docker)

From this folder:

```bash
docker compose up --build
```

Open:

- Frontend: http://localhost:5173
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

## Local development

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Vite proxies `/api` to `http://localhost:8000`.

### Tests

```bash
cd backend
pytest
```

## API endpoints

- `GET /api/assessments`
- `POST /api/assessments`
- `GET /api/assessments/{id}`
- `DELETE /api/assessments/{id}`
- `GET /api/billing/status`

Creating an assessment increments billing usage. When the limit is reached, API returns `402 Payment Required`.

## Notes

This is a portfolio MVP aligned with audit/assessment + billing workflow patterns. Stripe webhook integration can be added as a follow-up project.

---

## Solution Architecture Review (implementation-backed)

**Business problem:** Demonstrate an assessment workflow with enforceable per-plan usage limits and a simple front-to-back contract.

**Implemented flow (one line):** Vue 3/TypeScript SPA → FastAPI REST endpoints → SQLAlchemy assessment/billing records → SQLite → Assessment list + usage status.

**Architecture decisions**
- **Separation:** Vue handles interaction; FastAPI centralizes validation, assessment persistence and usage-limit decisions rather than trusting browser-side counters.
- **Contract & tests:** CRUD and billing-status APIs have pytest coverage; a limit breach is represented as an explicit HTTP 402 response.
- **Trade-off:** Local SQLite and Docker Compose keep the portfolio runnable; enterprise billing requires user/account identity, durable metering, concurrency-safe quota updates and a PSP.
- **Security & observability:** Add authentication, tenant isolation, audit logging, billing event reconciliation, request tracing and alerts before serving real organizations.
- **Evaluation:** Test concurrent assessment creation at a quota boundary, error rates, usage drift, API latency and database migration behavior.

**RAG status:** Not applicable; no LLM or vector search is implemented.

**Status:** Local full-stack portfolio MVP; paid billing and production multi-tenancy are outside scope.
