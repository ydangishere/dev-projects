"""
Script 1: Lu session TradingView sau khi dang nhap thu cong.
Dung Chrome (co san tai khoan Google).
"""
from playwright.sync_api import sync_playwright
import os

SESSION_FILE = os.path.join(os.path.dirname(__file__), "tradingview_session.json")


def save_session():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=False)
        context = browser.new_context()
        page = context.new_page()

        print("Opening Chrome...")
        page.goto("https://www.tradingview.com/", wait_until="networkidle")

        print("\n" + "=" * 50)
        print("MANUAL LOGIN:")
        print("1. Click 'Log in' on page")
        print("2. Choose 'Continue with Google'")
        print("3. Wait for TradingView to load (logged in)")
        print("4. Return here and press ENTER to save session")
        print("=" * 50 + "\n")

        input("Press ENTER after login complete...")

        context.storage_state(path=SESSION_FILE)
        print("Session saved to:", SESSION_FILE)

        browser.close()


if __name__ == "__main__":
    save_session()
