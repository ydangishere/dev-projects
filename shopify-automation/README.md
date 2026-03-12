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
