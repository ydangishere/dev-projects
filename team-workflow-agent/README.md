# Team Workflow Automation & AI Review

A **human-governed process automation backbone** for BA / PM / Designer / Developer, built from this [Figma workflow (node 218:30)](https://www.figma.com/design/eVmB2S0UTg8IP2yllKNH4O/temp?node-id=218-30&t=6eljU6Qq20O89JYw-4). Designed for teams experiencing unclear ownership, missed handoffs, requirement drift and schedule slips.

## Figma workflow reference

- **Original workflow diagram:** [Automation workflow — Figma node `218:30`](https://www.figma.com/design/eVmB2S0UTg8IP2yllKNH4O/temp?node-id=218-30&t=6eljU6Qq20O89JYw-4)
- This frame documents the collaboration and handoff process among **BA / PM / Designer / Developer**. Use it as the reference when changing workflow stages, ownership, notifications and approval gates.

## Quick start — Windows 11

```powershell
cd dev-projects\team-workflow-agent
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

Open **http://127.0.0.1:8010**. Requires Python 3.11+. Default local server listens only on `127.0.0.1`.

## Workflow & human responsibilities

1. **Create module:** PM/BA registers module, owner, deadline, Docs link; internal tracker becomes local Source of Truth.
2. **Definition of Ready:** PM/BA must complete business goal, user flow, business logic, edge cases and acceptance criteria. Approval opens Ready for Design and queues Designer notification.
3. **Wireframe draft:** Designer supplies real Figma URL → Wireframe Review; owner is notified.
4. **Requirement changes (at any stage except Done):** Change Log requires what/why, design & dev impacts and confirmation; prior status is invalidated, task goes back to Changes Requested and DoR must be reconfirmed.
5. **Design handoff:** Named approver + Figma handoff link → Ready for Dev. Developer notified.
6. **Technical review:** Dev checks constraints. With blockers: Blocked – Technical, optional explicitly requested GitHub Issue. Without: In Development → deployment URL → Done.

All decisions, stage transitions, change logs and notices are persisted and auditable in SQLite (`workspace/workflow.sqlite3`). This app does **not** silently grant approvals from Figma comments or AI recommendations.

## Optional integrations (edit `.env`, never commit credentials)

| Integration | Function | Requirement |
|---|---|---|
| Google Docs | Requirements link, human-edited DoR | Copy Docs link; comment ingestion not yet wired |
| Google Sheets | One-way tracker mirror using Google Sheets API | `GOOGLE_SERVICE_ACCOUNT_JSON`, `GOOGLE_SHEET_ID`; create a tab named `Modules` and share with service-account email |
| Figma | Linked wireframes/handoff, optional read-only text retrieval for Design Agent | `FIGMA_TOKEN`; requires node-specific `/design/...?...node-id=` URL; not a visual pixel inspection |
| GitHub | Create technical-constraint Issues | `GITHUB_REPOSITORY`, `GITHUB_TOKEN` with Issues write; optional, only on explicit click |
| Gmail / Workspace SMTP | Queue email notices & reminders | `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`; manually dispatch (or schedule) |
| Google Chat | Post to configured space webhook | `GOOGLE_CHAT_WEBHOOK`; posts to space, not member DMs |
| OpenAI | Requirements, Design & Technical specialist advisory reviews | `OPENAI_API_KEY`, optional `OPENAI_MODEL` |

**AI roles:** Requirements Agent checks DoR consistency; Design Review Agent compares design text/context to requirements; Technical Review Agent identifies development dependencies. They share records through one deterministic **Orchestrator** and produce advisory reports only. They do not replace PM approvals or human design decisions. This is a **multi-specialist AI workflow**, not independent autonomous agents with unsupervised permission to modify tools.

**Reminders:** Click `Check deadlines & queue reminders`, then `Send queued Gmail / Google Chat`. At most 3 reminders per person per status, spaced by at least `REMINDER_INTERVAL_DAYS` (default: 1 day). To automate daily, use Windows Task Scheduler to run `python app.py reminders` with working directory here. Automatic outbound sending is **off** unless `ENABLE_SCHEDULED_DELIVERY=1` is explicitly set. Outbox failed sends may be retried up to three times.

**Handoff to other agents:** `/modules/{id}/handoff.json` returns approved requirements, Figma link, change log and AI reports for an external Website Builder Agent/Codex workflow. It only becomes available after named design handoff approval. This is a read-only interoperability contract; automatic cross-agent job triggering isn't implemented.

## Test

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Limitations / security

- This is an **MVP for a trusted single operator on a local machine**; no OAuth login, role-based access control, CSRF defence or verified reviewer identity. Never expose port 8010 publicly.
- The SQLite database is the canonical internal tracker in this MVP. Google Sheets is a **one-way projection**, not an independently editable master. Do not edit Sheet rows and expect the local database to update.
- Google Docs comments are *not* ingested automatically and Google Sheets isn't synchronized until explicitly configured and synced.
- Figma text fetch is optional. It does not inspect images, geometry or visual defects.
- No secret keys, customer data or internal document contents should be committed to the public GitHub repo.
- No autonomous deployment or source code changes in this application; team members retain control over implementation.

---

## Solution Architecture Review (implementation-backed)

**Business problem:** A BA/PM/Designer/Developer team needs traceable requirements, named approvals, explicit handoffs and bounded AI assistance without giving agents final authority.

**Implemented flow (one line):** Module + requirements → Definition-of-Ready gate → Figma review → Named handoff approval → Technical review → Developer delivery URL → SQLite audit trail.

**Architecture decisions**
- **Control plane:** A deterministic Python/FastAPI workflow engine owns transitions, reminders and approval gates; SQLite is the single local source of truth. AI-generated advice never updates a project's approval status.
- **Integrations:** Optional read-only Figma text retrieval, GitHub issue creation on request, Google Sheets one-way export, manual SMTP/Google Chat dispatch and OpenAI specialist reviews. External integrations fail visibly when credentials are missing.
- **AI pattern:** Requirements, design and technical specialist prompts return advisory reports attached to a module; the human owner decides. Explicitly distinguish *multi-specialist orchestration* from unsupervised autonomous agents.
- **Quality & observability:** Event/change logs, state versioning, retry-capped outbox and unit tests support replayable investigation. Success indicators to measure in a pilot: missing handoffs, late approvals, unresolved blocker age, AI review usefulness and reminder failures.
- **Architecture trade-off:** Single-operator SQLite simplifies reproducibility and avoids premature infrastructure; a shared deployment would require identity verification, role-based authorization, CSRF protection, queue workers and credential isolation.

**RAG-style contextual retrieval (implemented, non-vector; one horizontal line):** `Module requirements + change log → Optional Figma API text retrieval → Bounded review context → OpenAI specialist analysis → Advisory report in SQLite → Human approval`

This is **retrieval-augmented prompting**, **not** a vector-database RAG pipeline: no embeddings, similarity index, hybrid search or reranker are implemented.

**Status:** Local, trusted-operator MVP; tests exist, but no production deployment, performance benchmark or enterprise multi-user security is demonstrated.
