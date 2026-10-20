import hashlib
import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

DB = os.getenv("DB_PATH", "/tmp/vietpay-demo.db")
app = FastAPI(title="VietPay Payment Simulator", description="Demo only; no real payment processing")

@contextmanager
def connection():
    con = sqlite3.connect(DB, timeout=30)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=30000")
    try:
        yield con
        con.commit()
    finally:
        con.close()

def init():
    with connection() as c:
        c.execute("CREATE TABLE IF NOT EXISTS payments (key TEXT PRIMARY KEY, tx_id TEXT NOT NULL, request_hash TEXT NOT NULL, payload TEXT NOT NULL)")
        c.execute("CREATE TABLE IF NOT EXISTS outbox (event_id TEXT PRIMARY KEY, payload TEXT NOT NULL, published INTEGER NOT NULL DEFAULT 0)")

init()

class Payment(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    merchant_id: str = Field(min_length=1, max_length=80)
    amount: int = Field(gt=0, le=1000000000)

@app.post("/payments")
def pay(p: Payment, idempotency_key: str = Header(..., min_length=1, max_length=128)):
    body = p.model_dump()
    digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    with connection() as c:
        try:
            c.execute("BEGIN IMMEDIATE")
            old = c.execute("SELECT request_hash,payload FROM payments WHERE key=?", (idempotency_key,)).fetchone()
            if old:
                if old[0] != digest:
                    raise HTTPException(409, "Idempotency key reused with different payload")
                return json.loads(old[1])
            result = {"transaction_id": str(uuid.uuid4()), "status": "SIMULATED_APPROVED", "created_at": time.time(), **body}
            encoded = json.dumps(result)
            c.execute("INSERT INTO payments VALUES (?,?,?,?)", (idempotency_key, result["transaction_id"], digest, encoded))
            event = {"event_id": str(uuid.uuid4()), **result}
            c.execute("INSERT INTO outbox(event_id,payload) VALUES (?,?)", (event["event_id"], json.dumps(event)))
            return result
        except sqlite3.OperationalError as exc:
            raise HTTPException(503, "Temporary database contention") from exc

@app.get("/payments/{key}")
def get_payment(key: str):
    with connection() as c:
        row = c.execute("SELECT payload FROM payments WHERE key=?", (key,)).fetchone()
    if not row:
        raise HTTPException(404, "Not found")
    return json.loads(row[0])

@app.get("/health")
def health():
    return {"ok": True}
