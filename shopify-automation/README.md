# Custom Shopify Features & Automation

Small Node.js service that receives **Shopify order webhooks** and syncs orders to an external database (Supabase). Use as a portfolio piece for **Shopify Automation & Integration** (e.g. Fiverr Gig 2).

## What this does

- **POST /webhooks/orders-create** — Receives Shopify `orders/create` webhook (HMAC-verified), saves order to Supabase.
- **GET /orders** — Returns stored orders (JSON).
- **GET /** — Simple HTML page to view orders.
- **POST /orders-create-mock** — Insert a test order (no Shopify; for demo/Postman).

## Quick start

1. **Clone this repo** and open the folder in terminal.

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Configure environment** — Copy `.env.example` to `.env` and set:
   - `SHOPIFY_WEBHOOK_SECRET` — From Shopify when you create the webhook.
   - `SUPABASE_URL` and `SUPABASE_ANON_KEY` — From [Supabase](https://supabase.com) Project Settings → API.

4. **Create the table** — In Supabase SQL Editor, run `supabase-orders-table.sql`.

5. **Run the server:**
   ```bash
   npm start
   ```
   Then open http://localhost:3000 to see the orders page.

## Connect real Shopify orders

You need a **public URL** so Shopify can send webhooks:

- **Option A (local):** Use [ngrok](https://ngrok.com) — run `ngrok http 3000` and use the HTTPS URL in Shopify.
- **Option B (deploy):** Deploy to [Render](https://render.com) (see `render.yaml`) and use the Render URL.

Full steps: see **WEBHOOK-SETUP.md**.

## Tech

- Node.js, Express
- Supabase (PostgreSQL)
- Shopify webhook HMAC verification

## License

ISC

---

## Solution Architecture Review (implementation-backed)

**Business problem:** Synchronize Shopify order events into a separate operational database while verifying inbound webhook authenticity.

**Implemented flow (one line):** Shopify orders/create webhook → Node.js/Express HMAC check → Order parsing → Supabase/PostgreSQL write → Orders API/HTML viewer.

**Architecture decisions**
- **Trust boundary:** Verify the incoming message authentication code before accepting external order state. Never use a public shared database key as an unrestricted privileged credential.
- **Event delivery:** Shopify can retry; use an event/order identifier, unique constraints and idempotent upserts for exactly-once *effects*, not assumptions about exactly-once message delivery.
- **Consistency:** Orders can arrive late or out of order, so a production sync should reconcile periodically and model state transitions explicitly.
- **Scaling/cost:** A single Express process is adequate for a demo; queue workers, backpressure, retry/dead-letter tracking and metrics support production bursts.
- **Evaluation:** Test invalid signatures, duplicate deliveries, Supabase outages, partial updates and delayed events.

**RAG status:** No Generative AI or RAG.

**Status:** Webhook-to-database integration example, not an independently audited Shopify application.
