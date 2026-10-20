import hmac
import json
import os
import sqlite3
import time
from fastapi import FastAPI, HTTPException, Request

app = FastAPI(title="TradingView Alert Receiver")
DB = os.environ.get("SHARED_DB", "/data/signals.db")

def connect():
    db = sqlite3.connect(DB, timeout=20)
    db.execute("PRAGMA busy_timeout=20000")
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alert_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        side TEXT NOT NULL,
        received_at INTEGER NOT NULL,
        payload TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS processed_pairs (
        pair_key TEXT PRIMARY KEY,
        created_at INTEGER NOT NULL
    )""")
    db.commit()
    return db

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/webhook/{secret}")
async def webhook(secret: str, request: Request):
    expected = os.getenv("WEBHOOK_SECRET", "")
    if not expected or not hmac.compare_digest(secret, expected):
        raise HTTPException(status_code=403, detail="Forbidden")
    raw = await request.body()
    if len(raw) > 8192:
        raise HTTPException(status_code=413, detail="Payload too large")
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="JSON required")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="JSON object required")
    alert_id = str(payload.get("alert_id", "")).strip()
    symbol = str(payload.get("symbol", "")).strip().upper()
    side = str(payload.get("side", "")).strip().upper()
    if not alert_id or not symbol or side not in ("BUY", "SELL") or len(alert_id) > 100 or len(symbol) > 40:
        raise HTTPException(status_code=422, detail="Require alert_id, symbol, side BUY/SELL")
    with connect() as db:
        db.execute("INSERT INTO alerts(alert_id,symbol,side,received_at,payload) VALUES(?,?,?,?,?)",
                   (alert_id, symbol, side, int(time.time()), json.dumps(payload)))
    return {"accepted": True, "status": "stored"}
