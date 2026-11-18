"""Phần Python mà agent Dana (dxa_agent.na) gọi tới.

Dana lo luồng xử lý và gọi LLM bằng reason().
Python chỉ làm những việc Dana gọi sang: tìm case (BM25 + vector, dùng lại rag.py),
dựng prompt, đọc JSON của LLM, kiểm chống bịa, ghép câu trả lời dự phòng.
Mọi giá trị trả về là kiểu cơ bản (str, list, dict) để Dana dùng thẳng.
"""
import json
import os
import re
import sys
from pathlib import Path

# lệnh `dana` không tự thêm thư mục này vào sys.path, nên thêm tay để import rag.py
sys.path.insert(0, str(Path(__file__).parent))

import rag  # noqa: E402

REFUSE = rag.REFUSE


def llm_ready() -> bool:
    """Có LLM thật để reason() gọi (Gemini qua cổng OpenAI, hoặc LLM giả khi kiểm thử)."""
    return bool(os.getenv("LOCAL_API_KEY")) or os.getenv("DANA_MOCK_LLM", "").lower() == "true"


def mode() -> str:
    if os.getenv("DANA_MOCK_LLM", "").lower() == "true":
        return "dana-mock"
    return "dana-gemini" if os.getenv("LOCAL_API_KEY") else "dana-offline"


def retrieve(question: str) -> dict:
    st = rag.state()
    r = rag.retrieve(question)
    return {
        "query_used": r["query_used"],
        "in_scope": bool(r["in_scope"] and r["cases"]),
        "case_ids": [st["cases"][i]["id"] for i in r["cases"]],
        "context": rag.build_context(st, r["cases"], r["chunks"]) if r["cases"] else "",
        "sources": rag.sources(st, r["cases"], r["chunks"]),
        "case_idx": list(r["cases"]),
    }


def refuse_text() -> str:
    return REFUSE


def log_unanswered(question: str, query_used: str, reason: str) -> bool:
    rag.log_unanswered(question, query_used, reason)
    return True


def answer_prompt(question: str, context: str) -> str:
    return rag.SYSTEM + """

Trả về ĐÚNG MỘT object JSON, không viết gì ngoài JSON, theo mẫu:
{"benh": "1 câu: bệnh gì và vì sao [Cxx]",
 "nguyen_nhan": "nguyên nhân [Cxx]",
 "cac_buoc": ["bước 1 [Cxx]", "bước 2 [Cxx]"],
 "thong_so": ["tên thông số: giá trị đơn vị [Cxx]"],
 "luu_y": "lưu ý nếu có, không có thì để trống",
 "ma_case": ["Cxx"]}
Mã case có thể là Cxx (lấy từ video) hoặc Txx (thợ nhập).
Nếu NGỮ CẢNH không trả lời được câu hỏi: {"khong_du_thong_tin": true}

""" + rag.PROMPT.format(ctx=context, q=question)


def parse_answer(raw) -> dict:
    """Đọc JSON từ câu của LLM. Đọc không được thì trả {} để agent dùng câu ghép khuôn."""
    if isinstance(raw, dict):
        return raw
    text = str(raw or "").strip()
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {}
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}
    if not isinstance(d, dict):
        return {}
    if d.get("khong_du_thong_tin"):
        return {"khong_du_thong_tin": True}
    out = {
        "benh": str(d.get("benh", "")).strip(),
        "nguyen_nhan": str(d.get("nguyen_nhan", "")).strip(),
        "cac_buoc": [str(x).strip() for x in d.get("cac_buoc", []) if str(x).strip()],
        "thong_so": [str(x).strip() for x in d.get("thong_so", []) if str(x).strip()],
        "luu_y": str(d.get("luu_y", "")).strip(),
        "ma_case": [str(x).strip() for x in d.get("ma_case", []) if str(x).strip()],
    }
    return out if out["benh"] and out["cac_buoc"] else {}


def render_answer(d: dict) -> str:
    lines = [d["benh"]]
    if d.get("nguyen_nhan"):
        lines.append(f"Nguyên nhân: {d['nguyen_nhan']}")
    lines.append("Cách sửa:")
    lines += [f"{i}. {s}" for i, s in enumerate(d["cac_buoc"], 1)]
    if d.get("thong_so"):
        lines.append("Thông số: " + "; ".join(d["thong_so"]))
    if d.get("luu_y"):
        lines.append(f"Lưu ý: {d['luu_y']}")
    return "\n".join(lines)


def check_answer(text: str, context: str, question: str, case_ids: list) -> list:
    """Bộ kiểm chống bịa của rag.py: số lạ, mã case lạ, không ghi mã case."""
    return rag.check_answer(text, context, question, set(case_ids))


def template_answer(case_idx: list) -> str:
    return rag.template_answer(rag.state(), list(case_idx))
