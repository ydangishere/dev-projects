# YouTube AI Agent — Hướng dẫn tiếng Việt

**[English](README.en.md) | [Trang chính](README.md)**

## 1. Mục đích và giới hạn

Theo dõi bình luận **công khai** trên kênh [@ydang7076](https://www.youtube.com/@ydang7076), chạy tự động lúc **00:00** và **12:00** hằng ngày (giờ Việt Nam, UTC+7), gửi bình luận mới tới Telegram Bot. Nếu điền OpenAI API Key, hệ thống phân loại câu hỏi và gợi ý trả lời; **mặc định không tự đăng trả lời** lên YouTube (có thể bật FAQ đã duyệt qua OAuth; xem cuối tài liệu). Không đọc tin nhắn riêng/inbox YouTube; không bảo đảm bắt được mọi phản hồi trong luồng bình luận cũ hoặc bình luận chờ duyệt.

**Luồng:** YouTube Data API v3 (đọc bình luận) → Apache Airflow (lên lịch) → SQLite (lưu ID chống trùng) → OpenAI *tùy chọn* (phân tích) → Telegram Bot API (thông báo).

Bản này là **MVP chạy trên máy Windows**, không phải một dịch vụ đã triển khai 24/7. Airflow task `Success` không có nghĩa chắc chắn Telegram đã gửi: nếu `notified: 0`, không có thông báo nào được gửi trong lần quét đó.

## 2. Yêu cầu

- Windows 11, Docker Desktop hỗ trợ Linux containers và Docker Compose.
- Google Cloud project đã bật **YouTube Data API v3**, API Key giới hạn dùng API này.
- Telegram Bot tạo bằng [@BotFather](https://t.me/BotFather), **Bot Token** và **Chat ID** dạng số. Phải nhấn **Start** trong chat với bot.
- OpenAI API Key là **tùy chọn**. Không có vẫn thông báo bình luận nếu `NOTIFY_ALL_COMMENTS=true`, nhưng không có AI gợi ý trả lời.

**Bảo mật:** Tuyệt đối không đưa `.env`, YouTube API Key, Telegram Bot Token, OpenAI API Key, mật khẩu Airflow hoặc file `comments.sqlite3` lên GitHub. Nếu từng để lộ token, nên thay token trước khi sử dụng lâu dài.

## 3. Cài đặt ban đầu

```powershell
cd "E:\AI\youtube\youtube-airflow-agent"  # ví dụ đường dẫn máy hiện tại
Copy-Item .env.example .env
notepad .env
```

Điền giá trị **thật** vào `.env` trên máy (không lưu trong repo):

```dotenv
YOUTUBE_CHANNEL_URL=https://www.youtube.com/@ydang7076
YOUTUBE_API_KEY=YOUR_PRIVATE_GOOGLE_API_KEY
TELEGRAM_BOT_TOKEN=YOUR_PRIVATE_TELEGRAM_TOKEN
TELEGRAM_CHAT_ID=YOUR_NUMERIC_CHAT_ID
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
NOTIFY_ALL_COMMENTS=true
MAX_PAGES=3
INITIAL_LOOKBACK_MINUTES=720
```

Cách tạo YouTube API Key: [Google Cloud](https://console.cloud.google.com/projectcreate) → tạo project → [YouTube Data API v3](https://console.cloud.google.com/apis/library/youtube.googleapis.com) → Enable → [Credentials](https://console.cloud.google.com/apis/credentials) → Create credentials → API key → giới hạn **API restrictions = YouTube Data API v3**. Không cần OAuth để đọc bình luận công khai.

Cách tạo Telegram Bot: mở [BotFather](https://t.me/BotFather) → `/newbot` → tên bot và username kết thúc bằng `bot` → cất Bot Token riêng → mở chat với bot → **Start**. Chạy lệnh dưới đây sau khi Airflow được khởi động để tìm Chat ID nếu chưa có:

```powershell
docker compose exec airflow python -m agent.telegram_setup
```

Sau khi sửa `.env` khi container đang chạy, cần tạo lại container để nhận biến môi trường mới: `docker compose up -d --force-recreate`.

## 4. Bật Airflow sau khi mở máy Windows

1. Mở **Docker Desktop**, bảo đảm hiển thị **Engine running**.
2. Mở PowerShell, chuyển vào thư mục chứa `docker-compose.yaml`.
3. Chạy:

```powershell
cd "E:\AI\youtube\youtube-airflow-agent"
docker compose up -d
docker compose ps
```

4. Truy cập <http://localhost:8080> trên **cùng máy**. Tài khoản mặc định của Airflow standalone là `admin`; mật khẩu được tạo trong lần đầu chạy, có thể đọc từ log hoặc file được Airflow sinh ra:

```powershell
docker compose logs airflow | Select-String "password"
docker compose exec airflow cat /opt/airflow/simple_auth_manager_passwords.json.generated
```

5. Tìm DAG `youtube_comment_ai_telegram` và **Unpause** nếu đang tạm dừng. Lịch đã đặt `schedule="0 */12 * * *"` theo `Asia/Ho_Chi_Minh`.

**Không cần tạo lại API Key, Telegram Bot hay Chat ID sau mỗi lần mở máy.** Với `restart: unless-stopped`, Docker có thể tự khởi chạy container khi Docker Engine khởi động trở lại; dùng `docker compose ps` để kiểm tra, và `docker compose up -d` nếu cần.

## 5. Tắt và mở lại

```powershell
# Tạm dừng Airflow, vẫn giữ dữ liệu
docker compose stop

# Mở lại
docker compose up -d

# Xem trạng thái
docker compose ps

# Xem log gần nhất
docker compose logs --tail=100 airflow
```

Muốn **tạm ngưng quét** mà vẫn mở giao diện: trong Airflow chọn **Pause** DAG `youtube_comment_ai_telegram`. Muốn bật lại: **Unpause**. Đóng trình duyệt **không** dừng Airflow. Đóng cửa sổ Docker Desktop chỉ dừng hệ thống nếu Docker Engine thực sự thoát; máy tắt/ngủ thì không quét.

**Không dùng `docker compose down -v`** vì nó xóa volumes, có thể làm mất SQLite chống trùng và mật khẩu/cấu hình Airflow. `docker compose down` *không có* `-v` giữ volume, nhưng tắt container và network.

Tự khởi động cùng Windows: Docker Desktop → Settings → General → bật **Start Docker Desktop when you sign in**. Sau đó xác nhận container tự trở lại bằng `docker compose ps`; nếu không, chạy `docker compose up -d`. Để hoạt động khi máy tắt, cần VPS/server chạy liên tục.

## 6. Thử kết nối và quét bình luận

```powershell
# Xác nhận kênh, bot, và gửi thử Telegram
docker compose exec airflow python -m agent.check_connections --send-test

# Quét ngay, không đợi 00:00 / 12:00
docker compose exec airflow python -m agent.monitor

# Kiểm tra đơn vị Python (không cần Docker)
python -m unittest discover -s tests -v
```

Bạn cũng có thể mở Airflow → DAG → **Trigger** để chạy thử thủ công. Kiểm tra **Task Instances → poll_analyze_notify → Logs**. Kết quả có `fetched` là số **mục bình luận mà lần chạy đã lấy được**, `notified` là **số thông báo đã gửi trong lần chạy**; ví dụ `fetched: 399, notified: 0` có nghĩa đọc được dữ liệu nhưng **không gửi** thông báo. Test Telegram thành công chỉ chứng minh đường gửi Telegram thông suốt, không chứng minh đã phát hiện bình luận mới.

Để thử thực tế: từ tài khoản khác, thêm bình luận **cấp cao nhất** (không phải reply vào thread cũ) trên một video công khai → kiểm tra bình luận đã hiện công khai → Trigger DAG hoặc chạy `python -m agent.monitor` như trên → xem `notified` và Telegram. YouTube có thể chậm hiển thị bình luận hoặc giữ lại để kiểm duyệt.

## 7. Lỗi thường gặp

| Triệu chứng | Nguyên nhân/cách xử lý |
| --- | --- |
| `docker` không nhận dạng | Cài Docker Desktop và mở lại PowerShell |
| Không kết nối được Docker daemon | Mở Docker Desktop, đợi `Engine running`, chạy `docker info` |
| Không vào được `localhost:8080` | `docker compose ps`, sau đó `docker compose logs --tail=100 airflow` |
| `OperationalError: unable to open database file` | Volume SQLite chưa có quyền ghi; chạy lệnh sửa bên dưới |
| DAG xanh nhưng Telegram không có tin mới | Xem `notified`; `0` = không gửi, kiểm tra cutoff, filter, bình luận công khai hoặc API chưa trả về bình luận |
| Test Telegram OK nhưng bình luận thật không báo | Chưa chứng minh đã phát hiện bình luận mới; thử bình luận cấp cao nhất + quét thủ công và kiểm tra log |
| `404` khi gọi Telegram | Kiểm tra Bot Token, không thêm dấu cách, kiểm tra bot đã được tạo |

Sửa quyền volume SQLite đã từng gặp trên máy Windows của dự án này:

```powershell
docker compose exec --user root airflow sh -c "chown -R 50000:0 /opt/airflow/state && chmod -R ug+rwX /opt/airflow/state"
```

Nếu dữ liệu đã được lưu trong volume, **đừng xóa volume** chỉ để sửa lỗi quyền ghi. Đường dẫn SQLite trong container: `/opt/airflow/state/comments.sqlite3`.

## 8. Những điểm cần biết trước khi chạy dài hạn

- Không bảo đảm bắt được tất cả reply trên thread cũ: `commentThreads.list` có thể trả một phần replies và chỉ quét tối đa `MAX_PAGES × 100` **threads** gần nhất/lần. Nếu kênh quá nhiều bình luận hoặc Docker ngừng lâu, có thể bỏ sót.
- `INITIAL_LOOKBACK_MINUTES=720` dùng để thiết lập mốc thời gian **trong lần chạy đầu tiên**. Mốc này được lưu trong SQLite và không tự thay đổi mỗi lần chạy; không phải giới hạn cứng 12 giờ cho những lần chạy sau.
- Mã lưu ID đã xử lý để hạn chế trùng. Nếu Telegram gửi thành công nhưng ứng dụng ngắt trước khi ghi SQLite, có thể gửi trùng sau đó.
- Tin nhắn YouTube riêng tư và bình luận bị giữ duyệt **không** được xử lý bằng API Key công khai. Mặc định không tự đăng bình luận; tùy chọn FAQ cố định có thể được kích hoạt sau khi cấp OAuth và duyệt nội dung.
- Không có OpenAI API Key: chương trình dùng bộ lọc câu hỏi đơn giản và vẫn gửi bình luận mới nếu `NOTIFY_ALL_COMMENTS=true`.
- Airflow `standalone` dành cho **demo/máy cá nhân**, không phải triển khai production có bảo mật toàn diện.
- Khi OpenAI được bật, nội dung bình luận sẽ được gửi đến dịch vụ OpenAI để phân tích; kiểm tra chính sách dữ liệu nếu cần.

Tham khảo: [YouTube API](https://developers.google.com/youtube/v3/docs/commentThreads/list) · [Telegram Bot API](https://core.telegram.org/bots/api) · [Apache Airflow](https://airflow.apache.org/docs/)


## Tự trả lời FAQ (tùy chọn; MẶC ĐỊNH TẮT)

Chỉ cho phép trả lời **bình luận cấp cao nhất** có chứa đúng một cụm từ FAQ đã được chủ kênh duyệt. Phần AI có thể phân loại/gợi ý trả lời qua Telegram như trước; **nội dung đăng tự động luôn lấy từ câu trả lời cố định trong `config/faq_rules.json`**, không đăng nguyên văn câu AI tự sinh. Không tự trả lời bình luận cũ quá 24 giờ, không trả lời phản hồi trong chuỗi cũ, tối đa 3 lần đăng mỗi phiên theo mặc định. Bình luận không khớp được chuyển qua Telegram để bạn tự trả lời.

**Cần OAuth 2.0 (cấp quyền tài khoản YouTube), không thể dùng API Key chỉ-đọc để đăng bình luận.** Dùng chính Google Cloud project đang bật YouTube Data API v3:

1. Vào Google Cloud → Google Auth Platform/OAuth consent screen, cấu hình tên ứng dụng và thêm tài khoản Google của bạn vào **Test users** nếu ứng dụng ở chế độ Testing. Tiếp tục vào Clients/Credentials → **Create OAuth client ID → Desktop app**, tải JSON vào thư mục dự án `secrets/client_secret.json` trên Windows. Không đưa file này lên GitHub.
2. Trên máy chạy dự án, trong PowerShell (cần Python 3 trên Windows), chạy `python -m agent.oauth_setup`. Trình duyệt mở trang Google, đăng nhập đúng tài khoản quản lý `@ydang7076`, cấp quyền và quay lại PowerShell. File `secrets/youtube_oauth.json` được tạo **chỉ trên máy của bạn**, có refresh token nhạy cảm.
3. Sửa `config/faq_rules.json` bằng cặp câu hỏi/cụm từ và câu trả lời ĐÃ DUYỆT. Ví dụ: `{"rules":[{"id":"thanks","triggers":["cảm ơn ad","cảm ơn bạn đã chia sẻ"],"reply":"Cảm ơn bạn đã xem video và ủng hộ kênh!"}]}`. Ban đầu file mặc định `{"rules":[]}`, nên sẽ không trả lời ai cả.
4. Trong `.env` đặt `AUTO_REPLY_ENABLED=true` và giữ `AUTO_REPLY_DRY_RUN=true` để **chạy thử mà không đăng**. Áp dụng cấu hình bằng `docker compose up -d --force-recreate`. Khi có bình luận mới khớp FAQ, log ghi `DRY RUN`. Chỉ sau khi kiểm tra nội dung, đổi `AUTO_REPLY_DRY_RUN=false` và chạy lại lệnh `--force-recreate` để cho phép đăng tự động.
5. Tắt tức thì việc đăng bằng `AUTO_REPLY_ENABLED=false` rồi `docker compose up -d --force-recreate`. Lịch Airflow vẫn **00:00 và 12:00**; không có đăng ngay khi người xem vừa bình luận.

Lỗi bất định sau khi gửi sẽ đánh dấu `error_needs_review`, **không tự thử lại** để tránh đăng trùng. Trạng thái nằm trong SQLite `reply_attempts`. Một lần tạo câu trả lời qua `comments.insert` dùng **50 quota units**. Ứng dụng OAuth ở trạng thái Testing có thể gặp refresh token hết hạn sau 7 ngày và phải cấp quyền lại. Mọi thay đổi file FAQ/secret chỉ thực hiện trên máy bạn. **Không upload `secrets/` hay `.env` lên repo.** Xem thêm [YouTube comments.insert](https://developers.google.com/youtube/v3/docs/comments/insert).
