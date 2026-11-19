"""Read-only mock bank API with synthetic data (samples/bank_mock.json).

Stands in for the bank's transaction, payment-switch, core-banking ledger, fraud/risk,
reconciliation, payout, merchant and log services. Every route is GET, requires the
service bearer token and the X-Tenant header, and returns 404 for another tenant's
data. Times are generated relative to the request time.

Run standalone: uvicorn app.mock_bank:app --port 8100   (BANK_API_TOKEN must be set)
"""

from __future__ import annotations

import hmac
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Header, HTTPException

DATA = Path(__file__).resolve().parents[1] / "samples/bank_mock.json"
ZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def create_mock_bank(token: str, data_path: Path = DATA, now=None) -> FastAPI:
    if not token:
        raise ValueError("Mock bank requires a service token")
    data = json.loads(data_path.read_text(encoding="utf-8"))
    bank = FastAPI(title="Mock bank API (synthetic)", docs_url=None, redoc_url=None)

    def clock():
        return now() if now else datetime.now(ZONE)

    def at(offset_hours):
        if offset_hours is None:
            return None
        return (clock() + timedelta(hours=offset_hours)).isoformat(timespec="seconds")

    def caller(authorization: str = Header(""), x_tenant: str = Header("")):
        expected = f"Bearer {token}"
        if not hmac.compare_digest(authorization.encode(), expected.encode()):
            raise HTTPException(401, "Service token required")
        if not x_tenant:
            raise HTTPException(400, "X-Tenant required")
        return x_tenant

    def record(transaction_id, tenant):
        item = data["transactions"].get(transaction_id)
        if not item:
            raise HTTPException(404, "Not found")
        merchant = data["merchants"][item["transaction"]["merchant_id"]]
        if merchant["tenant"] != tenant:
            raise HTTPException(404, "Not found")
        return item

    @bank.get("/v1/transactions/{transaction_id}")
    def transaction(transaction_id: str, tenant=Depends(caller)):
        item = record(transaction_id, tenant)["transaction"]
        return {
            "transaction_id": transaction_id,
            "merchant_id": item["merchant_id"],
            "amount": item["amount"],
            "currency": item["currency"],
            "status": item["status"],
            "channel": item["channel"],
            "created_at": at(item["created_offset_hours"]),
        }

    @bank.get("/v1/switch/{transaction_id}")
    def switch(transaction_id: str, tenant=Depends(caller)):
        return {"transaction_id": transaction_id, **record(transaction_id, tenant)["switch"]}

    @bank.get("/v1/ledger/{transaction_id}")
    def ledger(transaction_id: str, tenant=Depends(caller)):
        return {
            "transaction_id": transaction_id,
            "entries": [
                {"entry": e["entry"], "amount": e["amount"], "posted_at": at(e["offset_hours"])}
                for e in record(transaction_id, tenant)["ledger"]
            ],
        }

    @bank.get("/v1/risk/{transaction_id}")
    def risk(transaction_id: str, tenant=Depends(caller)):
        return {"transaction_id": transaction_id, **record(transaction_id, tenant)["risk"]}

    @bank.get("/v1/reconciliation/{transaction_id}")
    def reconciliation(transaction_id: str, tenant=Depends(caller)):
        item = record(transaction_id, tenant)["reconciliation"]
        if item is None:
            raise HTTPException(404, "No reconciliation record")
        return {
            "transaction_id": transaction_id,
            "batch_id": item["batch_id"],
            "status": item["status"],
            "matched": item["matched"],
            "value_date": at(item["value_offset_hours"]),
        }

    @bank.get("/v1/payouts/by-transaction/{transaction_id}")
    def payout(transaction_id: str, tenant=Depends(caller)):
        item = record(transaction_id, tenant)["payout"]
        if item is None:
            raise HTTPException(404, "No payout")
        body = {k: v for k, v in item.items() if k != "paid_offset_hours"}
        return {**body, "paid_at": at(item.get("paid_offset_hours"))}

    @bank.get("/v1/merchants/{merchant_id}")
    def merchant(merchant_id: str, tenant=Depends(caller)):
        item = data["merchants"].get(merchant_id)
        if not item or item["tenant"] != tenant:
            raise HTTPException(404, "Not found")
        return {"merchant_id": merchant_id, **{k: v for k, v in item.items() if k != "tenant"}}

    @bank.get("/v1/logs/{transaction_id}")
    def logs(transaction_id: str, tenant=Depends(caller)):
        return {
            "transaction_id": transaction_id,
            "events": [
                {"at": at(e["offset_hours"]), "service": e["service"], "event": e["event"]}
                for e in record(transaction_id, tenant)["logs"]
            ],
        }

    return bank


def _standalone():
    token = os.getenv("BANK_API_TOKEN", "")
    return create_mock_bank(token) if token else FastAPI(title="Set BANK_API_TOKEN")


app = _standalone()
