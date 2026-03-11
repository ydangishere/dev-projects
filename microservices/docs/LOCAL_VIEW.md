# Xem thử project microservices chạy local

## Bước 1: Bật PostgreSQL + Redis (Docker)

Mở terminal tại thư mục **microservices** (gốc repo):

```powershell
cd d:\microservices
npm run docker:up
```

(Lệnh này chạy `docker-compose -f infrastructure/docker-compose.yml up -d` — khởi động Postgres, Redis, Kafka, v.v. Lần đầu có thể mất vài phút tải image.)

Chỉ cần **Postgres** và **Redis** cho auth + people. Nếu muốn chỉ chạy 2 container đó, dùng:

```powershell
docker-compose -f infrastructure/docker-compose.yml up -d postgres redis
```

Đợi ~10–20 giây cho Postgres sẵn sàng.

---

## Bước 2: Cài dependency

```powershell
cd d:\microservices
npm install
```

---

## Bước 3: Chạy Auth service

Mở **một terminal**, chạy:

```powershell
cd d:\microservices
npm run dev:auth
```

(Nếu báo lỗi **port đã dùng** (EADDRINUSE): tắt app đang chiếm port 3001, hoặc trong `.env` đặt `PORT=3011` cho auth rồi chạy lại.)

Đợi thấy dòng kiểu: `Auth Service running on port 3001`.

**Xem thử:** mở trình duyệt → http://localhost:3001/health  
→ Thấy JSON `{"status":"ok","service":"auth-service"}` là OK.

---

## Bước 4: Chạy People service (terminal thứ hai)

Mở **terminal mới**, chạy:

```powershell
cd d:\microservices
npm run dev:people
```

Đợi thấy: `People Service running on port 3012`.

**Xem thử:** http://localhost:3012/health  
→ Thấy JSON có `"service":"people-service"` là OK.

---

## Link xem nhanh

| Service | Link |
|--------|------|
| Auth – health | http://localhost:3001/health |
| Auth – API | http://localhost:3001/api/auth/... |
| People – health | http://localhost:3012/health |
| People – API | http://localhost:3012/api/people |

---

## Dừng

- Dừng auth/people: trong từng terminal bấm **Ctrl+C**.
- Tắt Docker: `npm run docker:down` (tại gốc repo).
