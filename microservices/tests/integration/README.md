# Integration Tests

## Setup

Integration tests cần infrastructure đang chạy (PostgreSQL, Redis, Kafka, Elasticsearch).

### Start infrastructure trước khi chạy tests:

```bash
cd d:\microservices
npm run docker:up
```

## Running Tests

### Test tất cả services:

```bash
npm test
```

### Test từng service:

```bash
# Auth service
npm run test --workspace=services/auth-service

# People service
npm run test --workspace=services/people-service

# Case service
npm run test --workspace=services/case-service
```

## Test Coverage

Xem coverage report:

```bash
npm test -- --coverage
```

## Integration Test Flow

### 1. Auth Flow
- Register user → Login → Get profile

### 2. People Flow
- Create person → Check cache miss
- Get person again → Check cache hit
- Update person → Cache invalidated
- List people → Check pagination

### 3. Case Flow
- Create case → Auto-indexed to Elasticsearch
- Search cases → Full-text search
- Update case → Re-indexed
- Listen Kafka events from people-service

## Metrics to Monitor During Tests

- **Unit tests**: Test pass rate, coverage %
- **Integration tests**: 
  - Response time (latency)
  - Cache hit rate (Redis)
  - Kafka message delivery
  - Elasticsearch indexing lag
  - Database query time

## CI/CD Integration

Tests chạy tự động trong CI pipeline:
- PR → Unit tests
- Merge → Integration tests
- Deploy → Smoke tests
