# Deploy microservices-auth & microservices-people lên Render (làm tay)

Dùng **payment-api-db** và **payment-api-redis** có sẵn (1 DB free, 1 Redis free).

---

## Bước 0: Lấy thông tin DB và Redis

1. Vào [dashboard.render.com](https://dashboard.render.com) → **payment-api-db**.
2. Tab **Info** (hoặc **Connect**) → copy:
   - **Internal Database URL** (hoặc ghi lại: Host, Port, Database, User, Password).
3. Vào **payment-api-redis** (nếu có) → copy **Internal Redis URL** (hoặc Connection String).

Nếu không có Redis: people-service vẫn cần REDIS_URL; có thể tạo **Key-Value** (Redis) free: **+ New** → **Key-Value** → tạo xong copy connection string.

---

## Bước 1: Tạo Web Service – microservices-auth

1. **+ New** → **Web Service**.
2. **Connect repository**: chọn repo **microservices** (ydangishere/microservices), branch **main**.
3. Cấu hình:
   - **Name:** `microservices-auth`
   - **Region:** Oregon (hoặc giữ mặc định)
   - **Branch:** `main`
   - **Runtime:** **Docker**
   - **Dockerfile Path:** `./services/auth-service/Dockerfile`  
     (quan trọng: đúng đường dẫn này)
   - **Instance type:** Free
4. **Environment** – thêm biến (Add Environment Variable):

   | Key           | Value |
   |---------------|--------|
   | NODE_ENV      | production |
   | PORT          | 3001 |
   | DB_HOST       | *(Host từ payment-api-db)* |
   | DB_PORT       | 5432 |
   | DB_NAME       | *(Tên database, vd: payment_api_db)* |
   | DB_USER       | *(User từ payment-api-db)* |
   | DB_PASSWORD   | *(Password từ payment-api-db)* |
   | JWT_SECRET    | *(đặt 1 chuỗi bí mật dài, vd: my-super-secret-key-xyz-123)* |
   | JWT_EXPIRES_IN| 24h |

   Nếu Render có **Add from Database** → chọn **payment-api-db** để tự điền DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD; sau đó thêm tay: NODE_ENV, PORT, JWT_SECRET, JWT_EXPIRES_IN.

5. **Health Check Path:** `/health`
6. **Create Web Service** → đợi build & deploy. Thành công khi status **Deployed** và mở URL service → `/health` trả về JSON.

Ghi lại **JWT_SECRET** đã đặt (dùng cho people-service).

---

## Bước 2: Tạo Web Service – microservices-people

1. **+ New** → **Web Service**.
2. Connect cùng repo **microservices**, branch **main**.
3. Cấu hình:
   - **Name:** `microservices-people`
   - **Region:** Oregon
   - **Branch:** `main`
   - **Runtime:** **Docker**
   - **Dockerfile Path:** `./services/people-service/Dockerfile`  
     (đúng đường dẫn, không dùng `./Dockerfile`)
   - **Instance type:** Free
4. **Environment** – thêm biến:

   | Key           | Value |
   |---------------|--------|
   | NODE_ENV      | production |
   | PORT          | 3002 |
   | DB_HOST       | *(cùng Host như auth)* |
   | DB_PORT       | 5432 |
   | DB_NAME       | *(cùng DB như auth, vd: payment_api_db)* |
   | DB_USER       | *(cùng User)* |
   | DB_PASSWORD   | *(cùng Password)* |
   | REDIS_URL     | *(Internal Redis URL từ payment-api-redis hoặc Key-Value mới tạo)* |
   | KAFKA_ENABLED | false |
   | JWT_SECRET    | *(giống JWT_SECRET đã đặt ở auth)* |

5. **Health Check Path:** `/health`
6. **Create Web Service** → đợi build & deploy.

---

## Lưu ý

- **Cùng 1 DB (payment_api_db):** auth tạo bảng `users`, people tạo bảng `people` → không xung đột.
- **JWT_SECRET** phải giống nhau giữa auth và people (để people verify token do auth cấp).
- Sau khi tạo xong, mỗi lần **push lên branch main** → Render tự deploy (Auto-Deploy mặc định bật).
