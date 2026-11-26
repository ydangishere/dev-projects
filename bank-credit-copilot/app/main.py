"""FastAPI entry point: `uvicorn app.main:app --reload` then open http://127.0.0.1:8000."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .envfile import load_env_file
from .pipeline import CreditCopilot

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"
MAX_FILES = 8

load_env_file(ROOT / ".env")
app = FastAPI(title="Bank Credit Copilot (demo)", version="0.1.0")
copilot = CreditCopilot()


class PolicyQuestion(BaseModel):
    question: str = Field(min_length=2, max_length=500)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "provider": copilot.llm.provider, "policy_version": copilot.policy.version}


@app.get("/api/samples")
def samples() -> list[dict]:
    return copilot.list_samples()


@app.post("/api/assess/sample/{case_id}")
def assess_sample(case_id: str) -> dict:
    try:
        return copilot.assess_sample(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Không có hồ sơ mẫu {case_id}") from exc


@app.post("/api/assess")
async def assess_upload(files: list[UploadFile] = File(...)) -> dict:
    if not files or len(files) > MAX_FILES:
        raise HTTPException(status_code=400, detail=f"Gửi từ 1 đến {MAX_FILES} tệp PDF/TXT")
    payload = [(f.filename or "upload", await f.read()) for f in files]
    return copilot.assess_files(payload)


@app.post("/api/policy/ask")
def ask_policy(body: PolicyQuestion) -> dict:
    return copilot.ask_policy(body.question)


@app.get("/api/policy")
def policy() -> dict:
    return {"version": copilot.policy.version, "clauses": [c.to_dict() for c in copilot.policy.clauses]}


@app.get("/api/audit")
def audit(limit: int = 20) -> list[dict]:
    return copilot.audit.tail(max(1, min(limit, 100)))


@app.get("/samples/{folder}/{filename}")
def sample_file(folder: str, filename: str) -> FileResponse:
    base = copilot.settings.samples_dir.resolve()
    path = (base / folder / filename).resolve()
    if base not in path.parents or path.suffix != ".pdf" or not path.exists():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path, media_type="application/pdf")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
