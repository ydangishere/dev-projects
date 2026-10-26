"""Check the configured YouTube channel and Telegram bot, no secrets printed.

Usage: python -m agent.check_connections [--send-test]
"""
from __future__ import annotations

import argparse
import os

from agent.monitor import API_BASE, TELEGRAM_BASE, notify_telegram, request_json, resolve_channel_id


def check(send_test: bool = False) -> dict[str, str]:
    url = os.environ.get("YOUTUBE_CHANNEL_URL", "").strip()
    api_key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not url or not api_key:
        raise ValueError("YOUTUBE_CHANNEL_URL and YOUTUBE_API_KEY must be configured in .env")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN must be configured in .env")
    channel_id = resolve_channel_id(url, api_key)
    channel = request_json(
        f"{API_BASE}/channels", params={"part": "snippet", "id": channel_id, "key": api_key}
    )
    items = channel.get("items", [])
    if not items:
        raise RuntimeError("The channel was not found after resolving its ID")
    channel_title = str(items[0].get("snippet", {}).get("title", "Unknown"))
    bot = request_json(f"{TELEGRAM_BASE}/bot{token}/getMe")
    if bot.get("ok") is not True:
        raise RuntimeError("Telegram bot authentication failed")
    bot_name = str(bot.get("result", {}).get("username", "Unknown"))
    if send_test:
        if not chat_id:
            raise ValueError("TELEGRAM_CHAT_ID is required for --send-test; run agent.telegram_setup")
        notify_telegram(token, chat_id, f"✅ Kết nối thành công!\nYouTube: {channel_title}\nChannel ID: {channel_id}\nAirflow sẽ kiểm tra bình luận theo lịch sau khi bạn bật DAG.")
    return {"channel_title": channel_title, "channel_id": channel_id, "bot_username": bot_name,
            "telegram_test_sent": "yes" if send_test else "no"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--send-test", action="store_true")
    args = parser.parse_args()
    result = check(send_test=args.send_test)
    print("YouTube:", result["channel_title"])
    print("Channel ID:", result["channel_id"])
    print("Telegram bot: @" + result["bot_username"])
    print("Test message sent:", result["telegram_test_sent"])
