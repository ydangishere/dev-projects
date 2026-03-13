# TradingView Alerts → Telegram

App tự động mở TradingView, chụp từng alert, gửi qua Telegram.

---

## Bước 1: Cài đặt (chỉ làm 1 lần)

**Yêu cầu:** Python đã cài, Chrome đã cài trên máy.

Mở terminal/PowerShell, chạy:

```powershell
cd d:\AI\AIautomationbot
pip install -r requirements.txt
playwright install chromium
```

*(Trên Mac: dùng `python3` thay cho `python`, đường dẫn thư mục có thể khác)*

---

## Bước 2: Cấu hình Telegram (chỉ làm 1 lần)

**2.1.** Mở Telegram, tìm **@BotFather**, gửi `/newbot`.

**2.2.** Đặt tên bot → BotFather trả về **token** (dạng `123456789:ABCdef...`). Copy token.

**2.3.** Mở bot vừa tạo, nhấn **Start**, gửi tin nhắn bất kỳ (vd: `hi`).

**2.4.** Mở trình duyệt, truy cập (thay `<TOKEN>` bằng token thật):
```
https://api.telegram.org/bot<TOKEN>/getUpdates
```

**2.5.** Trong JSON, tìm `"chat":{"id":123456789}` → số đó là **chat_id**.

**2.6.** Mở file `telegram_config.py`, điền:
```python
TELEGRAM_CONFIG = {
    "bot_token": "token_cua_ban",
    "chat_id": "chat_id_cua_ban",
}
```

---

## Bước 3: Chạy app

**Windows:** Double-click `run_alerts.bat`

**Mac:** Mở Terminal, chạy:
```bash
cd /duong/dan/toi/AIautomationbot
chmod +x run_alerts.sh
./run_alerts.sh
```

---

## Bước 4: Đăng nhập TradingView (lần đầu hoặc khi hết phiên)

Khi chạy app:

**4.1.** Chrome sẽ mở trang TradingView.

**4.2.** Nếu chưa đăng nhập: bấm **Log in** → chọn **Email** hoặc **Google** → đăng nhập như bình thường.

**4.3.** Khi đã thấy trang chính (đã đăng nhập), chuyển sang cửa sổ terminal.

**4.4.** Nhấn **ENTER** trên bàn phím để lưu session.

**4.5.** App tiếp tục: mở panel Alerts, click từng alert, chụp màn hình, gửi qua Telegram.

---

## Bước 5: Nhận ảnh trên Telegram

Sau khi chạy xong, mở Telegram → chat với bot của bạn. Sẽ thấy 8 ảnh chụp các alert TradingView.

---

## Lưu ý

- **Session hết hạn:** Sau vài ngày/tuần có thể phải đăng nhập lại. Chạy lại app, làm lại Bước 4.
- **File `tradingview_session.json`:** Chứa cookie đăng nhập. Không chia sẻ, không đẩy lên git.
- **Chỉ gửi ảnh (không chạy lại):** Khi đã có ảnh trong `alert_screenshots/`, chạy `python send_alerts_telegram.py`.
