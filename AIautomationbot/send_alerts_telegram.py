"""
Gửi ảnh trong alert_screenshots/ qua Telegram tới chat_id đã cấu hình
Chạy khi đã có ảnh và đã cấu hình telegram_config.py
"""
import sys
import io
import os

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCREENSHOTS_DIR = os.path.join(SCRIPT_DIR, "alert_screenshots")

TELEGRAM_CONFIG = {"bot_token": "", "chat_id": ""}

try:
    from telegram_config import TELEGRAM_CONFIG as CUSTOM
    TELEGRAM_CONFIG.update(CUSTOM)
except ImportError:
    pass


def send_alerts_telegram():
    if not TELEGRAM_CONFIG["bot_token"] or not TELEGRAM_CONFIG["chat_id"]:
        print("Chưa cấu hình. Tạo telegram_config.py từ telegram_config.example.py")
        print("Điền bot_token và chat_id.")
        return

    paths = []
    for i in range(1, 9):
        p = os.path.join(SCREENSHOTS_DIR, f"alert_{i}.png")
        if os.path.exists(p):
            paths.append(p)

    if not paths:
        print(f"Không tìm thấy ảnh trong {SCREENSHOTS_DIR}")
        return

    token = TELEGRAM_CONFIG["bot_token"]
    chat_id = TELEGRAM_CONFIG["chat_id"]
    url = f"https://api.telegram.org/bot{token}/sendPhoto"

    for i, path in enumerate(paths, 1):
        try:
            with open(path, "rb") as f:
                r = requests.post(url, data={"chat_id": chat_id}, files={"photo": f}, timeout=30)
            if r.json().get("ok"):
                print(f"   Alert {i} -> đã gửi")
            else:
                print(f"   Alert {i} lỗi: {r.json().get('description', r.text)}")
        except Exception as e:
            print(f"   Alert {i} lỗi: {e}")

    print(f"\nĐã gửi {len(paths)} ảnh qua Telegram.")


if __name__ == "__main__":
    send_alerts_telegram()
