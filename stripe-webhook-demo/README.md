# Stripe Webhook Demo

FastAPI service that receives Stripe webhooks, verifies signatures, and stores events with idempotency. Built to demonstrate billing integration patterns for SaaS / assessment platforms.

## Stack

- **Python 3.12** + **FastAPI**
- **Stripe** webhook signature verification
- **SQLAlchemy** + SQLite (event audit log)
- **Docker Compose**
- **pytest**

## Features

- `POST /webhooks/stripe` — verify Stripe signature, handle events
- Supported events: `checkout.session.completed`, `invoice.paid`, `customer.subscription.updated`
- Idempotent processing (duplicate `event.id` returns `duplicate: true`)
- `GET /api/events` — audit log of processed webhooks
- `GET /health` — health check

## Quick start (local)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- API docs: http://localhost:8000/docs
- Events: http://localhost:8000/api/events

## Test with Stripe CLI

1. Install [Stripe CLI](https://stripe.com/docs/stripe-cli)
2. Login: `stripe login`
3. Forward webhooks to local server:

```powershell
stripe listen --forward-to localhost:8000/webhooks/stripe
```

4. Copy the **webhook signing secret** (`whsec_...`) from CLI output into `backend/.env`:

```
STRIPE_WEBHOOK_SECRET=whsec_...
```

5. Restart uvicorn, then trigger test events:

```powershell
stripe trigger checkout.session.completed
stripe trigger invoice.paid
```

6. Check stored events:

```powershell
curl http://localhost:8000/api/events
```

## Docker

```powershell
# from project root
$env:STRIPE_WEBHOOK_SECRET="whsec_your_secret"
docker compose up --build
```

## Tests

```powershell
cd backend
pytest -v
```

## API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/webhooks/stripe` | Stripe webhook endpoint (requires `Stripe-Signature` header) |
| GET | `/api/events` | List processed webhook events |
| GET | `/health` | Service health |

## Why this project

Demonstrates production-ready Stripe integration: signature verification, idempotency, event logging, and test workflow — aligned with billing microservice requirements in full-stack SaaS roles.
