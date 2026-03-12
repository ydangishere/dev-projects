# Shopify webhook setup (real orders → your server)

## Option A: Test locally with ngrok (quick)

1. **Install ngrok**  
   https://ngrok.com/download (or `winget install ngrok`)

2. **Start your server** (in this folder):
   ```powershell
   npm start
   ```

3. **In a second terminal**, run:
   ```powershell
   ngrok http 3000
   ```
   Copy the **HTTPS** URL (e.g. `https://abc123.ngrok-free.app`).

4. **Webhook URL** to use in Shopify:
   ```
   https://YOUR-NGROK-URL/webhooks/orders-create
   ```
   Example: `https://abc123.ngrok-free.app/webhooks/orders-create`

5. **In Shopify Admin:**  
   Settings → Notifications → Webhooks → Create webhook  
   - Event: **Order creation**  
   - Format: **JSON**  
   - URL: (paste the URL from step 4)  
   - Save. Shopify will show a **Signing secret** (or you get it when you create the webhook).

6. **Put the secret in `.env`:**
   ```env
   SHOPIFY_WEBHOOK_SECRET=the_secret_shown_in_shopify
   ```
   Restart: `npm start`.

7. Place a test order in your Shopify store; it should hit your server and appear in Supabase / http://localhost:3000.

---

## Option B: Deploy to Render (public URL 24/7)

1. Push this folder to a GitHub repo (or use Render's "Deploy from Git").

2. Go to https://render.com → New → Web Service.

3. Connect the repo, set:
   - **Build command:** `npm install` (or leave empty).
   - **Start command:** `npm start`
   - **Environment variables:** Add `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SHOPIFY_WEBHOOK_SECRET` (same as in `.env`).

4. Deploy. Render gives you a URL like `https://shopify-automation-xxx.onrender.com`.

5. **Webhook URL** for Shopify:
   ```
   https://YOUR-RENDER-URL/webhooks/orders-create
   ```

6. In Shopify: Settings → Notifications → Webhooks → Create webhook (Order creation, JSON, URL above). Copy the signing secret into `SHOPIFY_WEBHOOK_SECRET` in Render's environment and redeploy if needed.

---

## Summary

| Step | You do |
|------|--------|
| Get a public URL | ngrok (Option A) or deploy to Render (Option B) |
| Create webhook in Shopify | Order creation → URL = `https://YOUR-PUBLIC-URL/webhooks/orders-create` |
| Set secret in `.env` or Render | `SHOPIFY_WEBHOOK_SECRET=...` from Shopify |

After that, real orders will hit your server and be stored in Supabase.
