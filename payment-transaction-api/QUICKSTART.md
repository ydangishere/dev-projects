# Quick Start Guide

Get the Payment Transaction API running locally in under 5 minutes.

**What You're Running**: A production-ready payment processing API that prevents double-charges using idempotency keys—the same pattern used by Stripe, Square, and PayPal.

---

## 🚀 One Command to Rule Them All

```bash
cd order-concurrency-lab
docker compose up --build
```

**After containers start** (~1 minute), open browser:
- **http://localhost:8000/docs** ← Interactive API docs (test endpoints here!)
- **http://localhost:8000/** ← API health check

---

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- curl or similar HTTP client

## Step 1: Start Services

```bash
# Navigate to project directory
cd order-concurrency-lab

# Start all services (PostgreSQL, Redis, API)
docker-compose up -d

# Verify services are running
docker-compose ps
```

Expected output:
```
NAME                STATUS              PORTS
order-api-app       Up 30 seconds       0.0.0.0:8000->8000/tcp
order-api-db        Up 30 seconds       0.0.0.0:5432->5432/tcp
order-api-redis     Up 30 seconds       0.0.0.0:6379->6379/tcp
```

## Step 2: Verify API Health

```bash
curl http://localhost:8000/
```

Expected response:
```json
{
  "message": "Order/Payment API",
  "version": "1.0.0"
}
```

## Step 3: Process Your First Payment

```bash
curl -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: my-first-order-$(date +%s)" \
  -d '{
    "customerId": "customer_001",
    "items": [
      {"productId": "p1", "qty": 2},
      {"productId": "p2", "qty": 1}
    ]
  }'
```

Expected response (201 Created):
```json
{
  "orderId": "txn_a1b2c3d4",
  "status": "CREATED",
  "total": 120.5
}
```

**What just happened?** You processed a payment transaction. The API:
1. Validated the payment request
2. Stored the idempotency key in the database
3. Created the transaction
4. Returned transaction ID

## Step 4: Test Double-Charge Prevention (Idempotency)

Run the **exact same command** again. This simulates a customer clicking "Pay" twice:

```bash
# Rerun the exact same request
curl -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: my-first-order-$(date +%s)" \
  -d '{
    "customerId": "customer_001",
    "items": [
      {"productId": "p1", "qty": 2},
      {"productId": "p2", "qty": 1}
    ]
  }'
```

Expected response (200 OK with idempotentReplay flag):
```json
{
  "orderId": "txn_a1b2c3d4",
  "status": "CREATED",
  "total": 120.5,
  "idempotentReplay": true
}
```

**What just happened?** The API:
1. Detected the same idempotency key
2. Verified the request payload matches (via SHA256 hash)
3. Returned the **original transaction** without creating a duplicate
4. Customer was **NOT double-charged** ✅

This is exactly how Stripe prevents double-charges in production.

## Step 5: Retrieve Payment Transaction

```bash
curl http://localhost:8000/orders/txn_a1b2c3d4
```

**Use case**: Check payment status for customer payment history page or accounting reconciliation.

## Step 6: Confirm/Settle Payment

```bash
curl -X POST http://localhost:8000/orders/txn_a1b2c3d4/confirm
```

**Use case**: Move payment from "pending" to "settled" state (e.g., after bank confirmation or manual approval).

## Step 7: View Product Catalog (for E-commerce)

```bash
curl http://localhost:8000/products
```

Expected response:
```json
{
  "products": [
    {"id": "p1", "name": "Product 1", "price": 50.0},
    {"id": "p2", "name": "Product 2", "price": 20.5},
    {"id": "p3", "name": "Product 3", "price": 30.0}
  ]
}
```

**Use case**: Cached product prices for fast checkout page rendering.

## Additional Commands

### View Logs

```bash
# All services
docker-compose logs -f

# API only
docker-compose logs -f app

# Database only
docker-compose logs -f db
```

### Access Database

```bash
docker-compose exec db psql -U postgres -d orderdb

# View orders
SELECT * FROM orders;

# View idempotency keys
SELECT key, status FROM idempotency_keys;

# Exit
\q
```

### Access Redis

```bash
docker-compose exec redis redis-cli

# View all keys
KEYS *

# Get product cache
GET products:v1

# Exit
exit
```

### Run Tests

```bash
# Comprehensive endpoint tests
./test_all_endpoints.sh

# Concurrency tests
./test_concurrency.sh

# Both (PowerShell on Windows)
.\test_all_endpoints.ps1
.\test_concurrency.ps1
```

### Stop Services

```bash
# Stop but keep data
docker-compose stop

# Stop and remove containers (keeps volumes)
docker-compose down

# Stop and remove everything including data
docker-compose down -v
```

## Troubleshooting

### Port Already in Use

If port 8000, 5432, or 6379 is already in use:

```bash
# Find process using port (Linux/Mac)
lsof -i :8000

# Find process using port (Windows)
netstat -ano | findstr :8000

# Kill the process or change port in docker-compose.yml
```

### Database Connection Errors

```bash
# Check database is running
docker-compose ps db

# Restart database
docker-compose restart db

# View database logs
docker-compose logs db
```

### Redis Connection Errors

```bash
# Check Redis is running
docker-compose ps redis

# Restart Redis
docker-compose restart redis
```

## Next Steps

- Read the full [README.md](README.md) for API documentation
- Review [DEPLOYMENT.md](DEPLOYMENT.md) for production deployment
- Check [CHANGELOG.md](CHANGELOG.md) for version history

---

For issues or questions, refer to the main documentation or check the logs for detailed error messages.
