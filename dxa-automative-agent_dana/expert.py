"""Tab "Bổ sung kiến thức": thợ đăng nhập, nhập case mới, lưu, kho tri thức dựng lại ngay.

- Đăng nhập: so mã thợ (biến DXA_THO_CODE trong .env). Chưa đặt thì dùng mã mặc định của bản
  chạy thử là 1234 và in ra cửa sổ đen. Dùng thật thì đặt DXA_THO_CODE riêng.
- Quyền được kiểm ở MÁY CHỦ: mọi thao tác ghi đều cần token thợ, không chỉ ẩn tab trên giao diện.
- Case thợ nhập lưu ở data/knowledge_expert.json (mã T01, T02...). dxa.load_cases() tự đọc file này
  vì tên khớp knowledge*.json.
- Không xóa hẳn: gỡ case thì đặt status="rejected" (giống thợ đánh "Sai"), mọi thao tác ghi thêm
  một dòng vào data/knowledge_expert_history.jsonl để truy vết và khôi phục.
"""
import hmac
import json
import os
import re
import secrets
import sys
import threading
import time

import dxa
import gemini_client as G  # đọc .env, nên DXA_THO_CODE đặt trong .env cũng dùng được
import rag

EXPERT_FILE = dxa.DATA / "knowledge_expert.json"
HISTORY_FILE = dxa.DATA / "knowledge_expert_history.jsonl"
UNANSWERED_FILE = dxa.DATA / "unanswered.jsonl"

SYSTEMS = ["nhiên liệu", "đánh lửa", "động cơ", "điện", "khung sườn", "truyền động", "thân vỏ", "khác"]
TOKEN_TTL = 8 * 3600          # token thợ hết hạn sau 8 giờ
MAX_FAILS, LOCK_SECONDS = 5, 60  # sai mã 5 lần thì khóa đăng nhập 60 giây

_lock = threading.Lock()      # chỉ một lần lưu + dựng lại kho tại một thời điểm
_tokens = {}                  # token -> hạn dùng (giữ trong bộ nhớ, tắt máy chủ là hết)
_fails = {"n": 0, "until": 0.0}
_code = None
DEMO_CODE = "1234"            # mã mặc định cho bản chạy thử (máy chủ chỉ nghe trên máy này: 127.0.0.1)


# ---------------------------------------------------------------- đăng nhập
def tho_code():
    """Mã thợ: lấy từ DXA_THO_CODE, chưa có thì dùng mã mặc định của bản chạy thử."""
    global _code
    if _code is None:
        _code = os.getenv("DXA_THO_CODE", "").strip()
        if not _code:
            _code = DEMO_CODE
            print(f"[DXA] Mã đăng nhập thợ: {_code} (mặc định bản chạy thử, đổi bằng DXA_THO_CODE=... trong file .env)",
                  file=sys.stderr, flush=True)
    return _code


def login(code):
    """Đúng mã thì trả token, sai thì trả None. Sai nhiều lần liên tiếp thì khóa một lúc."""
    now = time.time()
    if now < _fails["until"]:
        raise PermissionError(f"Sai mã quá nhiều lần, thử lại sau {int(_fails['until'] - now)} giây")
    if not hmac.compare_digest(str(code or "").strip().encode(), tho_code().encode()):
        _fails["n"] += 1
        if _fails["n"] >= MAX_FAILS:
            _fails["n"], _fails["until"] = 0, now + LOCK_SECONDS
        return None
    _fails["n"] = 0
    token = secrets.token_urlsafe(32)
    _tokens[token] = now + TOKEN_TTL
    return token


def is_tho(token):
    exp = _tokens.get(token or "")
    if exp is None:
        return False
    if exp < time.time():
        _tokens.pop(token, None)
        return False
    return True


def logout(token):
    _tokens.pop(token or "", None)


# ---------------------------------------------------------------- đọc / ghi file
def _read():
    if EXPERT_FILE.exists():
        return json.loads(EXPERT_FILE.read_text(encoding="utf-8"))
    return {"_note": "Kiến thức do thợ nhập trên tab Bổ sung kiến thức. Mỗi case = Triệu chứng -> Nguyên nhân -> Cách sửa, "
                     "không gắn video. status=rejected nghĩa là đã gỡ, giữ lại để truy vết.", "cases": []}


def _write(d):
    tmp = EXPERT_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(EXPERT_FILE)  # ghi file tạm rồi đổi tên: tắt máy giữa chừng cũng không hỏng file


def _history(action, case):
    rec = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "action": action, "case": case}
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def list_cases(include_removed=False):
    cases = _read()["cases"]
    return cases if include_removed else [c for c in cases if c.get("status") != "rejected"]


def _next_id(cases):
    nums = [int(m.group(1)) for c in cases for m in [re.fullmatch(r"T(\d+)", c["id"])] if m]
    return f"T{(max(nums) + 1) if nums else 1:02d}"


# ---------------------------------------------------------------- kiểm dữ liệu thợ nhập
def _clean_list(xs, limit=20):
    out = []
    for x in xs or []:
        x = re.sub(r"\s+", " ", str(x)).strip()
        if x and x not in out:
            out.append(x[:200])
    return out[:limit]


def _clean_text(s, field, required=True, max_len=600):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    if required and len(s) < 3:
        raise ValueError(f"Chưa điền {field}")
    if len(s) > max_len:
        raise ValueError(f"{field} dài quá {max_len} ký tự")
    return s


def _clean_specs(specs):
    out = []
    for s in specs or []:
        name = _clean_text(s.get("name"), "tên thông số", max_len=100)
        value = _clean_text(s.get("value"), f"giá trị của {name}", required=False, max_len=60)
        if not value:
            raise ValueError(f"Thông số '{name}' chưa có giá trị")
        out.append({"name": name, "value": value, "unit": _clean_text(s.get("unit"), "đơn vị", required=False, max_len=30)})
    return out[:20]


def build_case(data, cases):
    """Biến dữ liệu form thành case đúng khuôn của kho (cùng trường với case lấy từ video)."""
    system = str(data.get("system") or "khác").strip()
    if system not in SYSTEMS:
        raise ValueError(f"Hệ thống phải là một trong: {', '.join(SYSTEMS)}")
    return {
        "id": _next_id(cases),
        "source": "tho",
        "video_id": None,
        "t": None,
        "system": system,
        "symptom": _clean_text(data.get("symptom"), "triệu chứng"),
        "cause": _clean_text(data.get("cause"), "nguyên nhân"),
        "fix": _clean_text(data.get("fix"), "cách sửa"),
        "parts": _clean_list(data.get("parts")),
        "tools": _clean_list(data.get("tools")),
        "vehicles": _clean_list(data.get("vehicles")),
        "specs": _clean_specs(data.get("specs")),
        "warnings": _clean_list(data.get("warnings")),
        "reviewed": True,
        "status": "active",
        "review_note": "Thợ nhập trên tab Bổ sung kiến thức",
        "author": _clean_text(data.get("author") or "thợ", "tên người nhập", max_len=60),
        "created_at": time.strftime("%Y-%m-%d %H:%M"),
        "from_question": _clean_text(data.get("from_question"), "câu hỏi gốc", required=False, max_len=500),
    }


# ---------------------------------------------------------------- dựng lại kho
def rebuild():
    """Dựng lại kho tri thức. Tầng vector Gemini chỉ dựng lại khi trước đó đang chạy
    (khi đó mọi vector cũ đã có trong cache, chỉ case mới tốn một lần gọi Gemini)."""
    was_gemini = rag._gemini_ok
    dxa.build()
    if was_gemini and G.available():
        try:
            import build_gemini
            build_gemini.main()
        except Exception as e:  # hết lượt / mất mạng: vẫn chạy, tạm dùng vector offline
            print(f"[expert] chưa dựng lại được vector Gemini: {e.__class__.__name__}", file=sys.stderr)
    rag.reset()
    return rag.mode()


def add_case(data):
    with _lock:
        d = _read()
        case = build_case(data, d["cases"])
        d["cases"].append(case)
        _write(d)
        _history("add", case)
        mode = rebuild()
    return case, mode


def remove_case(case_id):
    with _lock:
        d = _read()
        for c in d["cases"]:
            if c["id"] == case_id and c.get("status") != "rejected":
                c["status"] = "rejected"
                c["removed_at"] = time.strftime("%Y-%m-%d %H:%M")
                _write(d)
                _history("remove", c)
                rebuild()
                return c
    return None


# ---------------------------------------------------------------- câu chưa trả lời được
def unanswered(limit=50):
    """Câu khách hỏi mà DXA chưa trả lời được, gộp câu trùng, bỏ câu thợ đã bổ sung kiến thức."""
    if not UNANSWERED_FILE.exists():
        return []
    done = {rag.bare(c.get("from_question", "")) for c in list_cases()} - {""}
    rows = {}
    for line in UNANSWERED_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        key = rag.bare(r.get("question", ""))
        if not key or key in done:
            continue
        prev = rows.get(key)
        rows[key] = {**r, "count": (prev["count"] + 1) if prev else 1}
    return sorted(rows.values(), key=lambda r: r["ts"], reverse=True)[:limit]
