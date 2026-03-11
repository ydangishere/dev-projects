## Payment Transaction API

High-performance payment/order API with strict idempotency guarantees, double-charge prevention, and Redis caching.

- **Tech**: Python 3.11, FastAPI, PostgreSQL, Redis, Alembic, Docker.
- **Main features**: idempotent `POST /orders`, `GET /orders/{orderId}`, `POST /orders/{orderId}/confirm`, `GET /products`, structured logging, caching, and concurrency tests.
- **Original repo**: `https://github.com/ydangishere/payment-transaction-api`

For full API docs, deployment notes (Docker/Render), and performance details, see the original README on GitHub.

