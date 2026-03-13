"""
Script: Mở TradingView, click từng alert, chụp màn hình, gửi qua Telegram.
"""
import sys
import io
import os

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import requests
from playwright.sync_api import sync_playwright

SESSION_FILE = os.path.join(os.path.dirname(__file__), "tradingview_session.json")
SCREENSHOTS_DIR = os.path.join(os.path.dirname(__file__), "alert_screenshots")

TELEGRAM_CONFIG = {"bot_token": "", "chat_id": ""}
try:
    from telegram_config import TELEGRAM_CONFIG as CUSTOM
    TELEGRAM_CONFIG.update(CUSTOM)
except ImportError:
    pass


def send_telegram_screenshots(screenshot_paths):
    if not TELEGRAM_CONFIG["bot_token"] or not TELEGRAM_CONFIG["chat_id"]:
        print("Chưa cấu hình Telegram. Tạo telegram_config.py từ telegram_config.example.py")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_CONFIG['bot_token']}/sendPhoto"
    for i, path in enumerate(screenshot_paths, 1):
        try:
            with open(path, "rb") as f:
                r = requests.post(url, data={"chat_id": TELEGRAM_CONFIG["chat_id"]}, files={"photo": f}, timeout=30)
            if r.json().get("ok"):
                print(f"   Alert {i} -> đã gửi Telegram")
            else:
                print(f"   Alert {i} lỗi: {r.json().get('description')}")
        except Exception as e:
            print(f"   Alert {i} lỗi: {e}")
    return True


def run_alerts_screenshot():
    if not os.path.exists(SESSION_FILE):
        print("Chưa có session. Chạy save_session.py trước.")
        return

    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    screenshot_paths = []

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=False)
        context = browser.new_context(storage_state=SESSION_FILE)
        page = context.new_page()

        print("1. Mở TradingView...")
        page.goto("https://www.tradingview.com/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

        print("2. Mở panel Alerts (Alt+A)...")
        page.keyboard.press("Alt+a")
        page.wait_for_timeout(2500)

        alert_items = page.locator(
            '[class*="alert"] [class*="row"], [class*="alert"] [class*="item"], '
            '[class*="listRow"], [data-name="alerts-list"] > div, '
            '[class*="alerts-list"] > div, [class*="table"] [class*="row"]'
        ).all()

        if len(alert_items) < 4:
            alert_items = page.locator('div').filter(has_text="Stopped").all()[:8]

        count = min(len(alert_items), 8)
        print(f"3. Tìm thấy ~{count} alerts. Click từng cái, chụp màn hình...")

        for i in range(count):
            try:
                item = alert_items[i]
                item.scroll_into_view_if_needed()
                item.click()
                page.wait_for_timeout(1000)

                dialog = page.locator('[class*="dialog"], [role="dialog"], [class*="modal"]').first
                if dialog.is_visible():
                    dialog.screenshot(path=os.path.join(SCREENSHOTS_DIR, f"alert_{i+1}.png"))
                    screenshot_paths.append(os.path.join(SCREENSHOTS_DIR, f"alert_{i+1}.png"))
                    print(f"   Alert {i+1} -> alert_{i+1}.png")
                else:
                    page.screenshot(path=os.path.join(SCREENSHOTS_DIR, f"alert_{i+1}.png"))
                    screenshot_paths.append(os.path.join(SCREENSHOTS_DIR, f"alert_{i+1}.png"))
                    print(f"   Alert {i+1} -> alert_{i+1}.png (full page)")

                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
            except Exception as e:
                print(f"   Alert {i+1} lỗi: {e}")

        print(f"\n4. Đã chụp {len(screenshot_paths)} ảnh.")
        print("5. Gửi qua Telegram...")
        send_telegram_screenshots(screenshot_paths)

        input("\nNhấn ENTER để đóng trình duyệt...")
        browser.close()


if __name__ == "__main__":
    run_alerts_screenshot()
