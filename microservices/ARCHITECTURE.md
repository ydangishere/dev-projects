# Architecture Deep Dive

## 1. Microservices Architecture

### Context
Hệ thống chia nhỏ thành nhiều "nhà" (services) độc lập, mỗi service quản lý 1 domain riêng.

### Action
- **Auth Service**: Authentication & Authorization
- **People Service**: Quản lý people
- **Case Service**: Quản lý cases

Giao tiếp qua:
- **HTTP REST**: Synchronous (request-response)
- **Kafka Events**: Asynchronous (fire-and-forget)

### Result đo được
- ✅ Dễ scale từng service riêng
- ✅ Deploy độc lập (không sập cả hệ)
- ✅ Team có thể làm việc độc lập

### Roadblock hay gặp
- ❌ Gọi chéo nhiều → lag tăng, timeout
- ❌ Data consistency khó (distributed transactions)
- ❌ Debugging phức tạp (distributed tracing cần có)

### Metrics nhìn
- **P95 latency**: Độ trễ 95% requests
- **Timeout rate**: % requests timeout
- **Error rate 5xx**: Lỗi server

---

## 2. Kafka Integration

### Context
Cần "bắn thông báo" giữa services mà không cần gọi thẳng nhau (loose coupling).

### Action
- **Producer** (People Service): Publish events
  - `people.created`
  - `people.updated`
  - `people.deleted`
- **Consumer** (Case Service): Subscribe và xử lý events

### Result
- ✅ Giảm coupling (phụ thuộc)
- ✅ Xử lý async → không chặn main flow
- ✅ Chịu tải tốt (buffer trong Kafka)
- ✅ Replay events nếu cần

### Roadblock
- ❌ "Nửa thành công nửa thất bại": DB insert ok nhưng event fail → cần **idempotent consumer**
- ❌ Event ordering phức tạp (cần partition key)
- ❌ Consumer chậm → lag tăng

### Metrics
- **Consumer lag**: Số events chưa xử lý
- **Retry count**: Số lần retry event
- **Processing time**: Thời gian xử lý event
- **Dead-letter queue size**: Events fail nhiều lần

### Implementation trong project

**Publisher (People Service)**:
```typescript
// After DB insert
await publishEvent(Topics.PEOPLE_CREATED, {
  eventType: 'PersonCreated',
  timestamp: new Date().toISOString(),
  data: { id, firstName, lastName, email },
  metadata: { userId }
});
```

**Consumer (Case Service)**:
```typescript
// Listen events
await kafkaConsumer.subscribe({
  topics: ['people.created', 'people.updated', 'people.deleted'],
});

await kafkaConsumer.run({
  eachMessage: async ({ topic, message }) => {
    const event = JSON.parse(message.value);
    await handlePersonEvent(topic, event);
  }
});
```

---

## 3. Redis Caching

### Context
DB bị hit quá nhiều cho dữ liệu đọc lặp (ví dụ: get person/:id nhiều lần).

### Action
**Cache pattern: Cache-Aside (Lazy Loading)**

1. Request đến → Check Redis
2. **Cache hit**: Trả về ngay từ Redis
3. **Cache miss**: Query DB → Cache result → Return

**Invalidation strategy**:
- Update/Delete → Xóa cache
- TTL (Time To Live) → Auto expire

### Result
- ✅ Giảm DB load (70-90%)
- ✅ Giảm latency (Redis in-memory, rất nhanh)

### Roadblock
- ❌ Cache invalidation phức tạp (cache stale data)
- ❌ Cache stampede: Nhiều requests cùng lúc khi cache expire
- ❌ Memory limited → eviction

### Metrics
- **Cache hit rate**: % requests hit cache (mục tiêu: > 70%)
- **Eviction rate**: Số keys bị xóa do out of memory
- **DB QPS**: Queries per second (giảm nếu cache tốt)

### Implementation trong project

```typescript
// Get person with cache
const cacheKey = CacheKeys.person(id);
const cached = await redisClient.get(cacheKey);

if (cached) {
  logger.info('Cache hit');
  return JSON.parse(cached);
}

// Cache miss
const person = await pool.query('SELECT * FROM people WHERE id = $1', [id]);
await redisClient.setEx(cacheKey, 3600, JSON.stringify(person));
```

**Cache keys pattern**:
- `person:{id}` → Individual person
- `people:list:{page}:{limit}` → Paginated list

---

## 4. Elasticsearch

### Context
Search "gần đúng", filter phức tạp, full-text search (PostgreSQL LIKE chậm).

### Action
1. Khi tạo/update case → Index vào Elasticsearch
2. Search request → Query Elasticsearch (không query DB)

### Result
- ✅ Search nhanh (inverted index)
- ✅ Hỗ trợ fuzzy search, ranking, highlight
- ✅ Filter phức tạp (status + priority + keyword)

### Roadblock
- ❌ Index lag: Dữ liệu DB và ES không sync ngay
- ❌ Elasticsearch down → search không hoạt động
- ❌ Mapping complex → cần plan trước

### Metrics
- **Search latency**: Thời gian search (mục tiêu: < 100ms)
- **Index lag**: Độ trễ đồng bộ DB → ES
- **Error rate**: % search requests fail

### Implementation trong project

**Indexing**:
```typescript
// After create case in DB
await esClient.index({
  index: 'cases',
  id: caseData.id.toString(),
  document: caseData,
  refresh: true,
});
```

**Searching**:
```typescript
// Multi-match query với filters
const result = await esClient.search({
  index: 'cases',
  body: {
    query: {
      bool: {
        must: [
          { multi_match: { query: 'bug login', fields: ['title^2', 'description'] } },
          { term: { status: 'open' } },
          { term: { priority: 'high' } }
        ]
      }
    }
  }
});
```

---

## 5. Authentication/Authorization

### JWT (JSON Web Token)

#### Context
API stateless (không giữ session trên server) → dễ scale.

#### Action
1. **Login**: User gửi email/password → Server verify → Generate JWT
2. **Subsequent requests**: Client gửi `Authorization: Bearer <token>`
3. **Verify**: Server verify JWT signature → Extract user info

#### JWT Structure
```
Header.Payload.Signature

{
  "userId": 123,
  "email": "user@example.com",
  "role": "admin",
  "exp": 1234567890
}
```

#### Result
- ✅ Stateless → Scale dễ (không cần session store)
- ✅ Portable (dùng được cross-service)

#### Roadblock
- ❌ Token bị lộ → attacker dùng được cho đến khi expire
- ❌ Revoke token khó (vì stateless)
- ❌ Token size lớn hơn session ID

#### Metrics
- **401 rate**: % requests unauthorized
- **Token refresh success rate**: % refresh token thành công

#### Implementation
```typescript
// Generate token
const token = jwt.sign(
  { userId, email, role },
  JWT_SECRET,
  { expiresIn: '24h' }
);

// Verify token (middleware)
const decoded = jwt.verify(token, JWT_SECRET);
req.user = decoded;
```

### OAuth2 (Optional - chưa implement)

#### Context
Login bằng Google/Microsoft hoặc SSO (Single Sign-On).

#### Action
1. Redirect user → OAuth provider (Google)
2. User login → Provider trả về code
3. Exchange code → Access token
4. Get user info → Map vào user nội bộ

---

## 6. Database Design

### Database-per-Service Pattern

#### Context
Mỗi service có database riêng → loose coupling.

#### Databases
- `auth_db`: Users, credentials
- `people_db`: People data
- `case_db`: Cases data

#### Result
- ✅ Service độc lập (không share schema)
- ✅ Scale DB riêng từng service
- ✅ Change schema không ảnh hưởng services khác

#### Roadblock
- ❌ Cross-service queries khó (cần API calls hoặc events)
- ❌ Distributed transactions (ACID không đảm bảo)
- ❌ Data duplication có thể cần

---

## 7. Error Handling & Resilience

### Error Types
- **Operational errors**: Expected (validation, not found, unauthorized)
- **Programmer errors**: Bugs (null pointer, syntax)

### Strategy
1. **Custom error classes**: `NotFoundError`, `UnauthorizedError`, etc.
2. **Global error handler**: Catch tất cả errors trong middleware
3. **Logging**: Log với context (user, request, stack trace)

### Resilience Patterns (chưa implement, production nên có)
- **Circuit breaker**: Ngừng gọi service fail liên tục
- **Retry with exponential backoff**: Retry với delay tăng dần
- **Timeout**: Set timeout cho mọi operations
- **Bulkhead**: Isolate resources

---

## 8. Testing Strategy

### Unit Tests
- **Mục đích**: Test logic riêng lẻ (không cần DB/Redis/Kafka)
- **Mock**: Mock dependencies (database, external APIs)
- **Fast**: Chạy nhanh (< 1s cho toàn bộ suite)

### Integration Tests
- **Mục đích**: Test "đường ống thật" (Controller → Service → DB)
- **Real dependencies**: Spin PostgreSQL, Redis test containers
- **Slower**: Chậm hơn unit tests nhưng catch nhiều bugs hơn

### Metrics
- **Test pass rate**: % tests pass
- **Coverage**: Code coverage (mục tiêu: > 80%)
- **Flaky test rate**: Tests lúc pass lúc fail

---

## 9. Monitoring & Observability

### The Three Pillars

#### 1. Logs
- **Structured logging**: JSON format
- **Context**: Request ID, user ID, timestamp
- **Levels**: info, warn, error, debug

#### 2. Metrics
- **System**: CPU, memory, disk
- **Application**: Latency, throughput, error rate
- **Business**: Number of users, cases created

#### 3. Traces (chưa implement)
- **Distributed tracing**: Track request qua nhiều services
- **Tools**: Jaeger, Zipkin

### Key Metrics (Golden Signals)

#### Latency
- **P50**: 50% requests nhanh hơn X ms
- **P95**: 95% requests nhanh hơn X ms
- **P99**: 99% requests nhanh hơn X ms

#### Traffic
- **RPS**: Requests per second
- **Throughput**: Data processed per second

#### Errors
- **Error rate**: % requests fail
- **5xx rate**: Server errors

#### Saturation
- **CPU usage**: %
- **Memory usage**: %
- **DB connections**: Current/Max

---

## 10. Scalability Considerations

### Horizontal Scaling
- **Services**: Run multiple instances behind load balancer
- **Database**: Read replicas, sharding
- **Kafka**: Thêm partitions, consumers
- **Redis**: Redis Cluster

### Vertical Scaling
- Tăng CPU, RAM cho từng component

### Bottlenecks
1. **Database**: Slow queries, connection pool exhausted
2. **Kafka**: Consumer lag → cần scale consumers
3. **Redis**: Memory full → eviction → cache miss tăng
4. **Network**: Latency giữa services

---

## 11. Security Checklist

### Authentication/Authorization
- ✅ JWT với strong secret
- ✅ Token expiration (24h)
- ⚠️ Refresh token flow (chưa có)
- ⚠️ Rate limiting (chưa có)

### Data Protection
- ✅ Password hashing (bcrypt)
- ⚠️ HTTPS (production cần có)
- ⚠️ Data encryption at rest

### Infrastructure
- ⚠️ Kafka SASL authentication
- ⚠️ Elasticsearch xpack security
- ⚠️ PostgreSQL SSL
- ⚠️ Redis password

### Application
- ⚠️ Input validation (có basic, cần strong hơn)
- ⚠️ SQL injection prevention (dùng parameterized queries - OK)
- ⚠️ CORS configuration
- ⚠️ Rate limiting

---

## 12. Future Improvements

### Short-term
- [ ] API Gateway (Kong, Nginx)
- [ ] Refresh token flow
- [ ] Rate limiting
- [ ] Request ID tracking
- [ ] Health check improvements

### Medium-term
- [ ] Distributed tracing (Jaeger)
- [ ] Metrics collection (Prometheus + Grafana)
- [ ] Circuit breaker pattern
- [ ] Service mesh (Istio - optional)

### Long-term
- [ ] Kubernetes deployment
- [ ] Auto-scaling
- [ ] Multi-region setup
- [ ] Event sourcing pattern
- [ ] CQRS (Command Query Responsibility Segregation)

---

**Summary**: Hệ thống này đã có đầy đủ **fundamentals** của microservices architecture. Production-ready cần thêm monitoring, security hardening, và resilience patterns.
