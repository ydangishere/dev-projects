"""API hỏi đáp DXA (FastAPI). Bản Dana: câu hỏi được agent Dana (dxa_agent.na) trả lời.

Chạy:
    uvicorn api:app --reload --port 8000
Mở thử trên trình duyệt: http://localhost:8000/docs

Endpoint:
    GET  /                    giao diện web (ui/index.html)
    GET  /health             trạng thái: số case, chế độ gemini/offline, model
    POST /ask                 {"question": "...", "use_llm": true}
    GET  /cases/{case_id}     xem một case (vd C01, T01)

Tab "Bổ sung kiến thức" (chỉ thợ, kiểm quyền ở máy chủ bằng header Authorization: Bearer <token>):
    POST   /tho/login         {"code": "..."} -> {"token": "..."}
    POST   /tho/logout
    GET    /tho/me            còn đăng nhập không
    GET    /unanswered        câu chưa trả lời được, bỏ câu đã bổ sung
    GET    /tho/cases         case thợ đã nhập
    POST   /tho/cases         lưu case mới rồi dựng lại kho ngay
    DELETE /tho/cases/{id}    gỡ case (giữ lại trong file để truy vết)
"""
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

import dxa
import dxa_dana
import expert
import gemini_client as G
import rag


@asynccontextmanager
async def lifespan(app):
    rag.state()  # nạp index một lần khi khởi động
    expert.tho_code()  # chưa đặt DXA_THO_CODE thì in mã thợ ra cửa sổ đen
    try:
        dxa_dana._load_agent()  # nạp agent Dana một lần (mất vài giây)
    except Exception as e:
        print(f"[api] Chưa nạp được agent Dana: {e}")
    yield


app = FastAPI(title="DXA – Trợ lý sửa xe máy (Dana)", version="1.0", lifespan=lifespan)


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
    source: Optional[str] = None       # "video" hoặc "tho" (thợ nhập)
    author: Optional[str] = None
    created_at: Optional[str] = None


class AskOut(BaseModel):
    question: str
    query_used: str
    answer: str
    refused: bool
    near: bool = False                 # trả lời bằng case gần nhất (câu hỏi chưa khớp hẳn)
    seconds: float = 0                 # tổng thời gian trả lời
    seconds_accent: float = 0          # phần thời gian gọi Gemini thêm dấu cho câu gõ không dấu
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
    return {"ok": True, "engine": "dana", "mode": rag.mode(), "cases": len(st["cases"]), "chunks": len(st["chunks"]),
            "videos": len(st["videos"]), "llm_model": G.LLM_MODEL if G.available() else None,
            "embed_model": G.EMBED_MODEL if rag.mode() == "gemini" else "offline TF-IDF"}


@app.post("/ask", response_model=AskOut)
def ask(body: AskIn):
    q = body.question.strip()
    t0 = time.perf_counter()
    res = dxa_dana.ask(q) if body.use_llm else rag.answer(q, use_llm=False)
    res["seconds"] = round(time.perf_counter() - t0, 2)
    res["seconds_accent"] = round(rag.accent_seconds.pop(q, 0.0), 2)
    print(f"[DXA] trả lời trong {res['seconds']} giây (thêm dấu {res['seconds_accent']} giây, "
          f"trả lời bởi {res['answered_by']}): {q[:60]}", file=sys.stderr, flush=True)
    return {k: res.get(k) for k in AskOut.model_fields}


@app.get("/cases/{case_id}")
def get_case(case_id: str):
    st = rag.state()
    for c in st["cases"]:
        if c["id"].lower() == case_id.lower():
            title, when, link = dxa.origin(st["videos"], c)
            return {**c, "link": link, "video_title": title, "time": when}
    raise HTTPException(404, f"Không có case {case_id}")


# ---------------------------------------------------------------- tab Bổ sung kiến thức (chỉ thợ)
def _token(authorization: Optional[str]) -> str:
    return (authorization or "").removeprefix("Bearer ").strip()


def require_tho(authorization: Optional[str] = Header(None)):
    """Kiểm quyền ở máy chủ: không có token thợ hợp lệ thì trả 401, dù ai đó gọi thẳng API."""
    if not expert.is_tho(_token(authorization)):
        raise HTTPException(401, "Cần đăng nhập thợ")


class LoginIn(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)


class SpecIn(BaseModel):
    name: str = Field(..., max_length=100)
    value: str = Field(..., max_length=60)
    unit: str = Field("", max_length=30)


class CaseIn(BaseModel):
    symptom: str = Field(..., max_length=600)
    cause: str = Field(..., max_length=600)
    fix: str = Field(..., max_length=600)
    system: str = "khác"
    parts: list[str] = []
    tools: list[str] = []
    vehicles: list[str] = []
    specs: list[SpecIn] = []
    warnings: list[str] = []
    author: str = Field("thợ", max_length=60)
    from_question: str = Field("", max_length=500)
    video_url: str = Field("", max_length=300)   # link YouTube thợ gắn (không bắt buộc)
    video_at: str = Field("", max_length=12)     # thời điểm phút:giây, vd 4:01


@app.post("/tho/login")
def tho_login(body: LoginIn):
    try:
        token = expert.login(body.code)
    except PermissionError as e:
        raise HTTPException(429, str(e))
    if not token:
        raise HTTPException(401, "Sai mã thợ")
    return {"token": token, "role": "tho"}


@app.post("/tho/logout")
def tho_logout(authorization: Optional[str] = Header(None)):
    expert.logout(_token(authorization))
    return {"ok": True}


@app.get("/tho/me", dependencies=[Depends(require_tho)])
def tho_me():
    return {"role": "tho", "systems": expert.SYSTEMS}


@app.get("/unanswered", dependencies=[Depends(require_tho)])
def unanswered(limit: int = 50):
    return expert.unanswered(limit)


@app.get("/tho/cases", dependencies=[Depends(require_tho)])
def tho_cases():
    return expert.list_cases()[::-1]


@app.post("/tho/cases", dependencies=[Depends(require_tho)])
def tho_add_case(body: CaseIn):
    try:
        case, mode = expert.add_case(body.model_dump())
    except ValueError as e:
        raise HTTPException(422, str(e))
    st = rag.state()
    return {"case": case, "mode": mode, "cases": len(st["cases"])}


@app.delete("/tho/cases/{case_id}", dependencies=[Depends(require_tho)])
def tho_remove_case(case_id: str):
    c = expert.remove_case(case_id)
    if not c:
        raise HTTPException(404, f"Không có case thợ nhập {case_id}")
    return {"removed": c["id"]}
