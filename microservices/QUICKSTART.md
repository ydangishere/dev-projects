# Quick Start Guide

Hướng dẫn chạy dự án trong **5 phút**.

## Bước 1: Start Infrastructure

```powershell
# Folder: d:\microservices
npm run docker:up
```

Đợi ~30 giây để các services khởi động. Check health:

```powershell
# PostgreSQL
docker exec ms-postgres pg_isready -U admin

# Redis
docker exec ms-redis redis-cli ping

# Elasticsearch
curl http://localhost:9200/_cluster/health

# Kibana (optional UI)
# Open: http://localhost:5601
```

## Bước 2: Install Dependencies

```powershell
# Folder: d:\microservices
npm install
```

## Bước 3: Setup Environment

```powershell
# Copy .env.example thành .env cho các services
Copy-Item services\auth-service\.env.example services\auth-service\.env
Copy-Item services\people-service\.env.example services\people-service\.env
Copy-Item services\case-service\.env.example services\case-service\.env
```

## Bước 4: Build Shared Package

```powershell
# Folder: d:\microservices
npm run build --workspace=shared
```

## Bước 5: Start Services

Mở **3 terminals** riêng:

**Terminal 1 - Auth Service (Port 3001)**
```powershell
cd d:\microservices
npm run dev:auth
```

**Terminal 2 - People Service (Port 3002)**
```powershell
cd d:\microservices
npm run dev:people
```

**Terminal 3 - Case Service (Port 3003)**
```powershell
cd d:\microservices
npm run dev:case
```

## Bước 6: Test hệ thống

### Option 1: Dùng Web UI (Dễ nhất! 🎉)

```powershell
# Mở file HTML trong browser
cd d:\microservices\admin-ui
start index.html
```

Sau đó:
1. Register/Login
2. Create people
3. Create cases
4. Search với Elasticsearch
5. Check console để xem cache hits, Kafka events!

### Option 2: Dùng API trực tiếp (curl/Postman)

#### Test APIs

### 6.1 Register User

```powershell
curl -X POST http://localhost:3001/api/auth/register `
  -H "Content-Type: application/json" `
  -d '{\"email\":\"test@example.com\",\"password\":\"password123\",\"full_name\":\"Test User\"}'
```

### 6.2 Login

```powershell
curl -X POST http://localhost:3001/api/auth/login `
  -H "Content-Type: application/json" `
  -d '{\"email\":\"test@example.com\",\"password\":\"password123\"}'
```

**Copy JWT token từ response!**

### 6.3 Create Person (với token)

```powershell
$token = "your-jwt-token-here"

curl -X POST http://localhost:3002/api/people `
  -H "Content-Type: application/json" `
  -H "Authorization: Bearer $token" `
  -d '{\"first_name\":\"John\",\"last_name\":\"Doe\",\"email\":\"john@example.com\"}'
```

### 6.4 Get Person (cache hit lần 2)

```powershell
# Lần 1: Cache miss → query DB
curl -H "Authorization: Bearer $token" http://localhost:3002/api/people/1

# Lần 2: Cache hit → Redis
curl -H "Authorization: Bearer $token" http://localhost:3002/api/people/1
```

Check logs để thấy "Cache hit" message!

### 6.5 Create Case

```powershell
curl -X POST http://localhost:3003/api/cases `
  -H "Content-Type: application/json" `
  -H "Authorization: Bearer $token" `
  -d '{\"title\":\"Bug in login\",\"description\":\"Users cannot login\",\"status\":\"open\",\"priority\":\"high\",\"person_id\":1}'
```

### 6.6 Search Cases (Elasticsearch)

```powershell
curl -H "Authorization: Bearer $token" "http://localhost:3003/api/cases/search?q=login&status=open"
```

## Bước 7: Verify Kafka Events

Check logs của **Case Service terminal** - bạn sẽ thấy message:

```
{"timestamp":"...","level":"info","service":"kafka","message":"Received event","topic":"people.created"}
```

Điều này chứng tỏ Case Service đã nhận được event từ People Service qua Kafka!

## Bước 8: Check Kibana (optional)

1. Mở browser: http://localhost:5601
2. Menu → Dev Tools
3. Query Elasticsearch:

```json
GET /cases/_search
{
  "query": {
    "match": {
      "title": "login"
    }
  }
}
```

## Troubleshooting

### Services không start được?

```powershell
# Check infrastructure
npm run docker:logs

# Restart infrastructure
npm run docker:down
npm run docker:up
```

### Port đã dùng?

Check ports:
```powershell
netstat -ano | findstr "3001"
netstat -ano | findstr "3002"
netstat -ano | findstr "3003"
```

Kill process nếu cần:
```powershell
taskkill /PID <process-id> /F
```

### Database connection error?

```powershell
# Check PostgreSQL
docker exec -it ms-postgres psql -U admin -d auth_db -c "\dt"
docker exec -it ms-postgres psql -U admin -d people_db -c "\dt"
docker exec -it ms-postgres psql -U admin -d case_db -c "\dt"
```

## Next Steps

✅ Đã chạy thành công? Tuyệt vời!

Tiếp theo:
1. Đọc `README.md` để hiểu kiến trúc tổng quan
2. Đọc `ARCHITECTURE.md` để deep dive từng component
3. Chạy tests: `npm test`
4. Explore code trong `services/`

## Commands Tổng hợp

```powershell
# Infrastructure
npm run docker:up       # Start all infrastructure
npm run docker:down     # Stop all infrastructure
npm run docker:logs     # View logs

# Development
npm run dev:auth        # Start auth service
npm run dev:people      # Start people service
npm run dev:case        # Start case service

# Build & Test
npm run build           # Build all services
npm test                # Run all tests
npm test -- --coverage  # Run with coverage
```

## Architecture Quick Reference

```
Auth Service (3001)  →  JWT tokens
People Service (3002) →  CRUD + Redis cache + Kafka publish
Case Service (3003)   →  CRUD + Elasticsearch + Kafka consume

Infrastructure:
- PostgreSQL: 5432 (3 databases)
- Redis: 6379 (cache)
- Kafka: 9092 (events)
- Elasticsearch: 9200 (search)
- Kibana: 5601 (UI)
```

Chúc code vui! 🚀
