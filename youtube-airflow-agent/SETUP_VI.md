# Cấu hình kênh YouTube @ydang7076 → Telegram

Kênh đã điền trong `.env.example`: `https://www.youtube.com/@ydang7076`. Khi có YouTube API key, chương trình tự chuyển @handle sang Channel ID chính xác theo API chính thức.

## Chưa kết nối thật

Link YouTube và Telegram username là thông tin công khai, **không** cho phép bot đọc bình luận với đầy đủ quyền hoặc gửi tin nhắn Telegram. Bạn tự giữ API key/token trong `.env`, không gửi qua chat, không commit lên GitHub.

## Cần làm trên Windows 11

1. Cài Docker Desktop và bật engine; giải nén ZIP. Mở PowerShell trong thư mục `youtube-airflow-agent`.
2. Tạo Google Cloud project, bật **YouTube Data API v3**, tạo **API key** cho việc đọc bình luận công khai: https://console.cloud.google.com/apis/library/youtube.googleapis.com . Giới hạn API key theo YouTube Data API v3 và hạn chế theo IP nếu phù hợp mô hình triển khai.
3. Mở https://t.me/BotFather, gửi `/newbot`, tạo bot riêng và giữ kín token. Mở bot vừa tạo, bấm Start hoặc nhắn `/start`. Username Telegram cá nhân không thay thế numeric chat ID.
4. Chạy `Copy-Item .env.example .env` và `notepad .env`; điền `YOUTUBE_API_KEY`, `TELEGRAM_BOT_TOKEN` (tuỳ chọn `OPENAI_API_KEY` nếu muốn AI phân loại và đề xuất trả lời). Đã điền sẵn `YOUTUBE_CHANNEL_URL`.
5. Chạy `docker compose up -d`.
6. Lấy numeric Telegram chat ID bằng `docker compose exec airflow python -m agent.telegram_setup`; sửa `TELEGRAM_CHAT_ID` trong `.env`, sau đó chạy `docker compose up -d --force-recreate`.
7. Chạy `docker compose exec airflow python -m agent.check_connections --send-test`. Nhận được tin nhắn kiểm tra trong Telegram là kết nối bot đúng. Đây **chưa phải bằng chứng có bình luận mới**.
8. Vào http://localhost:8080, đăng nhập Airflow bằng tài khoản trong `docker compose logs airflow`, tìm DAG `youtube_comment_ai_telegram`, bỏ trạng thái Pause và kích hoạt thử.

**Lưu ý:** Cron `0 */12 * * *` chạy theo múi giờ `Asia/Ho_Chi_Minh`; Airflow chỉ chạy lịch khi máy chủ còn hoạt động. Máy chạy Docker cần bật liên tục để kiểm tra mỗi 12 giờ (00:00 và 12:00 theo giờ Việt Nam). Các bình luận cũ hơn mốc thiết lập đầu tiên (mặc định 12 giờ) không được thông báo hàng loạt. Có thể bỏ sót những reply mới ở các thread quá cũ do giới hạn API/polling. Bản đầu chỉ đề xuất câu trả lời, không tự đăng.
