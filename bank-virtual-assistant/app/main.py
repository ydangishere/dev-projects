"""FastAPI app: chat API + a simulated core-banking REST API in one process.

    uvicorn app.main:app --reload      ->  http://127.0.0.1:8000

`/core/v1/*` stands in for the bank's service layer (in a real bank: Java/Spring Boot
services in front of the core). Set CORE_BASE_URL to make the assistant call that API
over HTTP instead of in-process.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .agent import Assistant
from .audit import AuditLog
from .core_bank import CoreBankingService, CoreError
from .core_client import HttpCoreClient, InProcessCoreClient
from .envfile import load_env_file
from .llm import LLMConfig

ROOT = Path(__file__).resolve().parents[1]
load_env_file(ROOT / ".env")

core_service = CoreBankingService(show_demo_otp=os.getenv("DEMO_SHOW_OTP", "true").lower() == "true")
core_client = (HttpCoreClient(os.environ["CORE_BASE_URL"]) if os.getenv("CORE_BASE_URL")
               else InProcessCoreClient(core_service))
audit = AuditLog(Path(os.getenv("AUDIT_PATH", ROOT / "data" / "audit.jsonl")))
assistant = Assistant(core_client, audit, LLMConfig.from_env())

app = FastAPI(title="Bank Virtual Assistant (demo)", version="0.1.0")


def core_http_error(exc: CoreError) -> HTTPException:
    status = 404 if exc.code.endswith("NOT_FOUND") else 422
    return HTTPException(status_code=status, detail={"code": exc.code, "message": exc.message})


# ---- simulated core-banking API ----------------------------------------------------------
core = APIRouter(prefix="/core/v1", tags=["simulated core banking"])


class TransferRequest(BaseModel):
    account_id: str
    beneficiary_id: str
    amount: int = Field(gt=0)
    note: str = Field(default="", max_length=120)


class OtpRequest(BaseModel):
    otp: str = Field(min_length=4, max_length=8)


@core.get("/accounts/{account_id}/balance")
def core_balance(account_id: str) -> dict:
    try:
        return core_service.get_balance(account_id)
    except CoreError as exc:
        raise core_http_error(exc) from exc


@core.get("/accounts/{account_id}/transactions")
def core_transactions(account_id: str, start: datetime | None = None, end: datetime | None = None,
                      category: str | None = None, limit: int | None = None) -> list[dict]:
    try:
        return core_service.list_transactions(account_id, start, end, category, limit)
    except CoreError as exc:
        raise core_http_error(exc) from exc


@core.get("/customers/{customer_id}/beneficiaries")
def core_beneficiaries(customer_id: str) -> list[dict]:
    try:
        return core_service.list_beneficiaries(customer_id)
    except CoreError as exc:
        raise core_http_error(exc) from exc


@core.post("/transfers")
def core_create_transfer(body: TransferRequest) -> dict:
    try:
        return core_service.create_transfer(body.account_id, body.beneficiary_id, body.amount, body.note)
    except CoreError as exc:
        raise core_http_error(exc) from exc


@core.post("/transfers/{transfer_id}/confirm")
def core_confirm_transfer(transfer_id: str, body: OtpRequest) -> dict:
    try:
        return core_service.confirm_transfer(transfer_id, body.otp)
    except CoreError as exc:
        raise core_http_error(exc) from exc


@core.post("/transfers/{transfer_id}/cancel")
def core_cancel_transfer(transfer_id: str) -> dict:
    try:
        return core_service.cancel_transfer(transfer_id)
    except CoreError as exc:
        raise core_http_error(exc) from exc


app.include_router(core)


# ---- assistant API -------------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = Field(default=None, max_length=64)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "llm_provider": assistant.llm.provider,
            "core": "http" if isinstance(core_client, HttpCoreClient) else "in-process"}


@app.get("/api/me")
def me() -> dict:
    balance = core_service.get_balance(assistant.account_id)
    return {"customer": core_service.customer["name"], **balance}


@app.post("/api/chat")
def chat(body: ChatRequest) -> dict:
    session_id = body.session_id or uuid.uuid4().hex
    return {"session_id": session_id, **assistant.handle(session_id, body.message)}


@app.post("/api/transfers/{transfer_id}/confirm")
def confirm(transfer_id: str, body: OtpRequest) -> dict:
    """Called by the OTP form in the UI, never by the assistant."""
    try:
        result = core_service.confirm_transfer(transfer_id, body.otp)
        audit.write("transfer_confirmed", {"transfer_id": transfer_id, "amount": result["amount"],
                                           "beneficiary": result["beneficiary"]["account_masked"]})
        return result
    except CoreError as exc:
        audit.write("transfer_confirm_failed", {"transfer_id": transfer_id, "code": exc.code})
        raise core_http_error(exc) from exc


@app.post("/api/transfers/{transfer_id}/cancel")
def cancel(transfer_id: str) -> dict:
    try:
        result = core_service.cancel_transfer(transfer_id)
        audit.write("transfer_cancelled", {"transfer_id": transfer_id})
        return result
    except CoreError as exc:
        raise core_http_error(exc) from exc


@app.get("/api/audit")
def audit_tail(limit: int = 30) -> list[dict]:
    return audit.tail(max(1, min(limit, 100)))


@app.get("/")
def index() -> FileResponse:
    return FileResponse(ROOT / "static" / "index.html")


app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
