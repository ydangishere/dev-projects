"""Display Telegram chat IDs after you have sent /start to your own bot.

Run: docker compose exec airflow python -m agent.telegram_setup
"""
import json
import os
from agent.monitor import request_json, TELEGRAM_BASE

token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
if not token:
    raise SystemExit("Set TELEGRAM_BOT_TOKEN in .env")
data = request_json(f"{TELEGRAM_BASE}/bot{token}/getUpdates", params={"limit": 20, "timeout": 0})
chats = {}
for update in data.get("result", []):
    msg = update.get("message") or update.get("edited_message") or {}
    chat = msg.get("chat") or {}
    if "id" in chat:
        chats[str(chat["id"])] = chat.get("title") or chat.get("first_name") or "Unknown"
print(json.dumps(chats, indent=2, ensure_ascii=False))
if not chats:
    print("No chat found. Send /start to your bot on Telegram, then rerun.")
