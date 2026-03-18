# Mini Payment Gateway Simulation

Demo payment flow: create order → redirect → callback → verify → update DB.

## Tech Stack

- Next.js (App Router)
- TypeScript
- TailwindCSS
- SQLite

## Usage Guide (Start to Finish)

### 1. Clone / Pull

```bash
# If cloning from remote
git clone <repository-url>
cd nextjs-payment

# If already have the project, pull latest
git pull
```

### 2. Install Dependencies

```bash
cd nextjs-payment
npm install
```

### 3. Run the App

```bash
npm run dev
```

App runs at http://localhost:3000

### 4. Test Payment Flow

1. Open http://localhost:3000
2. Click **Pay Now**
3. You are redirected to the fake payment page
4. Click **Success** or **Fail**
5. You are redirected to the result page showing the status
6. Click **Return** to go back to homepage

### 5. Check DB via Admin Page

1. Open http://localhost:3000/admin
2. Click **View Orders**
3. See the table of all orders with ID and status (pending / success / fail)
4. Click **Return** to go back to homepage

### 6. Security Check (Optional)

- Open http://localhost:3000/api/orders directly → returns **401 Unauthorized** (no token)
- Admin page sends token when calling API → returns data

---

## Flow

1. **Homepage** – Click "Pay Now" → `POST /api/create-payment` → create order (pending) → redirect to `/payment?id=xxx`
2. **Fake Payment** – Success/Fail buttons → `POST /api/callback` → redirect to `/result?id=xxx`
3. **Callback** – Verify signature, idempotency check, update DB
4. **Result** – Fetch status → display success / fail

## Project Structure

```
/app
  /api
    create-payment/route.ts
    callback/route.ts
    get-status/route.ts
    orders/route.ts         # Admin API (protected by token)
  /admin/page.tsx          # Admin – View DB
  /payment/page.tsx
  /result/page.tsx
  page.tsx
/lib
  db.ts
```

## Key Concepts

- **Redirect vs Webhook**: Redirect for UI flow, webhook for backend confirmation
- **Idempotency**: Callback may be called multiple times; only update when status = pending
- **Verification**: Signature check to prevent fake callbacks
