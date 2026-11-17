"""API hỏi đáp DXA (FastAPI).

Chạy:
    uvicorn api:app --reload --port 8000
Mở thử trên trình duyệt: http://localhost:8000/docs

Endpoint:
    GET  /                    giao diện web (ui/index.html)
    GET  /health             trạng thái: số case, chế độ gemini/offline, model
    POST /ask                 {"question": "...", "use_llm": true}
    GET  /cases/{case_id}     xem một case (vd C01)
    GET  /unanswered          các câu chưa trả lời được (cho thợ xem)
"""
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

import dxa
import gemini_client as G
import rag


@asynccontextmanager
async def lifespan(app):
    rag.state()  # nạp index một lần khi khởi động
    yield


app = FastAPI(title="DXA – Trợ lý sửa xe máy", version="1.0", lifespan=lifespan)


class AskIn(BaseModel):
    question: str = Field(..., min_length=2, max_length=500, examples=["binh xang con buong ga ma ga khong ve"])
    use_llm: bool = True


class Source(BaseModel):
    type: str
    id: str
    video_title: str
    time: str
    link: str
    symptom: Optional[str] = None
    cause: Optional[str] = None
    fix: Optional[str] = None
    specs: list = []
    reviewed: Optional[bool] = None
    review_note: Optional[str] = None
    text: Optional[str] = None


class AskOut(BaseModel):
    question: str
    query_used: str
    answer: str
    refused: bool
    answered_by: str
    mode: str
    warnings: list[str]
    sources: list[Source]


UI = Path(__file__).parent / "ui" / "index.html"


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(UI)


@app.get("/health")
def health():
    st = rag.state()
    return {"ok": True, "mode": rag.mode(), "cases": len(st["cases"]), "chunks": len(st["chunks"]),
            "videos": len(st["videos"]), "llm_model": G.LLM_MODEL if G.available() else None,
            "embed_model": G.EMBED_MODEL if rag.mode() == "gemini" else "offline TF-IDF"}


@app.post("/ask", response_model=AskOut)
def ask(body: AskIn):
    res = rag.answer(body.question.strip(), use_llm=body.use_llm)
    return {k: res[k] for k in AskOut.model_fields}


@app.get("/cases/{case_id}")
def get_case(case_id: str):
    st = rag.state()
    for c in st["cases"]:
        if c["id"].lower() == case_id.lower():
            return {**c, "link": rag.case_link(c), "video_title": st["videos"][c["video_id"]]["title"]}
    raise HTTPException(404, f"Không có case {case_id}")


@app.get("/unanswered")
def unanswered(limit: int = 50):
    p = dxa.DATA / "unanswered.jsonl"
    if not p.exists():
        return []
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    return rows[-limit:][::-1]
