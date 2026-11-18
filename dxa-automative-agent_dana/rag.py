"""Hỏi đáp DXA bằng Gemini: tìm kiếm lai (BM25 + Gemini vector) rồi để Gemini viết câu trả lời.

Luồng một câu hỏi:
  1. Câu gõ không dấu  -> Gemini thêm dấu (chỉ được thêm dấu, không được đổi chữ).
  2. Tìm case + đoạn video bằng BM25 và Gemini vector, gộp thứ hạng bằng RRF.
  3. Cổng từ chối: dùng lại dxa.in_scope() đã chỉnh trên eval.py. Ngoài phạm vi thì không gọi LLM, không đoán.
  4. Gemini viết câu trả lời CHỈ từ ngữ cảnh, ghi [Cxx] sau mỗi ý.
  5. Kiểm câu trả lời: con số nào không có trong ngữ cảnh, hoặc [Cxx] lạ -> bỏ câu của LLM, trả bản ghép khuôn.
  6. Luôn gắn link video nhảy đúng giây (code tự gắn, không nhờ LLM).

Không có GEMINI_API_KEY thì tự chạy bản offline (TF-IDF + khuôn), giống `dxa.py ask`.

Dùng thử:  python rag.py "binh xang con buong ga ma ga khong ve"
"""
import json
import pickle
import re
import sys
import time
import unicodedata

import numpy as np

import dxa
import gemini_client as G
from vector_store import VectorStore

TOP_CASES = 3
TOP_CHUNKS = 3
RRF_K = 60

_state = _store = None
_gemini_ok = False
_accent_cache = {}


# ---------------------------------------------------------------- nạp
class _Unpickler(pickle.Unpickler):
    """`python dxa.py build` lưu class dưới tên __main__.BM25. Nạp từ file khác (rag, api) thì đổi về dxa.BM25."""

    def find_class(self, module, name):
        if module == "__main__":
            module = "dxa"
        return super().find_class(module, name)


def load_state():
    with open(dxa.OUT / "state.pkl", "rb") as f:
        return _Unpickler(f).load()


def state():
    """Nạp state.pkl một lần. Tầng Gemini chỉ bật khi đã build_gemini.py và khớp với state hiện tại."""
    global _state, _store, _gemini_ok
    if _state is None:
        _state = load_state()
        meta_p = dxa.OUT / "gemini_meta.json"
        if G.available() and meta_p.exists():
            meta = json.loads(meta_p.read_text(encoding="utf-8"))
            same = meta.get("case_ids") == [c["id"] for c in _state["cases"]] and meta.get("chunks") == len(_state["chunks"])
            if same and meta.get("embed_model") == G.EMBED_MODEL:
                _store = VectorStore()
                _gemini_ok = True
            else:
                print("[rag] index Gemini cũ hơn state.pkl hoặc khác model: chạy lại build_gemini.py. Tạm dùng vector offline.",
                      file=sys.stderr)
    return _state


def mode():
    state()
    return "gemini" if _gemini_ok else "offline"


def reset():
    """Bỏ kho đang nạp trong bộ nhớ, để lần hỏi sau đọc kho vừa dựng lại (sau khi thợ lưu kiến thức)."""
    global _state, _store, _gemini_ok
    _state, _store, _gemini_ok = None, None, False


# ---------------------------------------------------------------- câu không dấu
def bare(s):
    """Bỏ dấu, chữ thường, chỉ giữ chữ và số: dùng để so 'có cùng chữ cái không'."""
    s = unicodedata.normalize("NFD", s.lower().replace("đ", "d").replace("Đ", "d"))
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]", "", s)


def has_accents(q):
    return any(unicodedata.category(ch) == "Mn" for ch in unicodedata.normalize("NFD", q)) or "đ" in q.lower()


ACCENT_PROMPT = """Câu dưới đây là tiếng Việt gõ không dấu, nói về sửa xe máy.
Hãy thêm dấu cho đúng. CHỈ thêm dấu: không thêm, bớt, đổi hay sắp xếp lại chữ nào.
Thuật ngữ thợ hay dùng: bình xăng con, buông ga, cò mổ, bánh cam, sên cam, xupap, piston, bugi, phao xăng, rơ le, xi nhan, côn, nồi, sườn, gấp, đùm, dè.
Trả JSON: {{"query": "<câu đã thêm dấu>"}}

Câu: {q}"""


def restore_accents(q):
    """Gõ không dấu -> có dấu. Nếu Gemini đổi chữ (không chỉ thêm dấu) thì giữ câu gốc."""
    if has_accents(q) or not G.available():
        return q
    if q not in _accent_cache:
        out = q
        try:
            cand = str(G.generate(ACCENT_PROMPT.format(q=q), temperature=0, json_mode=True).get("query", "")).strip()
            if cand and bare(cand) == bare(q):
                out = cand
        except Exception as e:
            print(f"[rag] không thêm dấu được: {e}", file=sys.stderr)
        _accent_cache[q] = out
    return _accent_cache[q]


# ---------------------------------------------------------------- tìm kiếm
def _rrf(rank_lists, k=RRF_K):
    score = {}
    for ranks in rank_lists:
        for r, i in enumerate(ranks):
            score[i] = score.get(i, 0.0) + 1.0 / (k + r + 1)
    return sorted(score.items(), key=lambda x: -x[1])


def _bm25_rank(bm, queries, n=20):
    s = np.max([bm.scores(dxa.tokens(x)) for x in queries], axis=0)
    order = [int(i) for i in np.argsort(-s)[:n] if s[i] > 0]
    return order, s


def _vec_rank(kind, query, n=20):
    st = state()
    if _gemini_ok:
        try:
            qv = G.embed([query], task="RETRIEVAL_QUERY")[0]
            return [i for i, _ in _store.search(kind, qv, n)]
        except Exception as e:  # mất mạng hoặc hết lượt Gemini: tạm dùng vector offline
            print(f"[rag] Gemini embedding lỗi, dùng vector offline: {e.__class__.__name__}", file=sys.stderr)
    E = st["E_cases"] if kind == "cases" else st["E_chunks"]
    s = E @ st["vec"].encode([query])[0]
    return [int(i) for i in np.argsort(-s)[:n]]


def retrieve(q, top_cases=TOP_CASES, top_chunks=TOP_CHUNKS):
    st = state()
    q2 = restore_accents(q)
    queries = [q] if q2 == q else [q, q2]

    case_bm, _ = _bm25_rank(st["bm25_cases"], queries)
    chunk_bm, _ = _bm25_rank(st["bm25_chunks"], queries)
    cases = _rrf([case_bm, _vec_rank("cases", q2)])[:top_cases]
    chunks = _rrf([chunk_bm, _vec_rank("chunks", q2)])[:top_chunks]

    return {
        "question": q,
        "query_used": q2,
        "in_scope": any(dxa.in_scope(st, x) for x in queries),
        "cases": [i for i, _ in cases],
        "chunks": [i for i, _ in chunks],
        "mode": mode(),
    }


# ---------------------------------------------------------------- ngữ cảnh + câu trả lời
def case_link(c):
    return dxa.origin({}, c)[2] if not dxa.from_video(c) else dxa.yt_link(c["video_id"], c["t"])


def chunk_link(ch):
    return dxa.yt_link(ch["video_id"], ch["start"])


def spec_text(c):
    return "; ".join(f'{s["name"]}: {s["value"]} {s["unit"]}'.strip() for s in c.get("specs", []))


def build_context(st, case_idx, chunk_idx):
    parts = []
    for i in case_idx:
        c = st["cases"][i]
        head = (f'(video: {st["videos"][c["video_id"]]["title"]}, phút {dxa.mmss(c["t"])})' if dxa.from_video(c)
                else f'(thợ nhập ngày {c.get("created_at", "")[:10]})')
        lines = [f'[{c["id"]}] {head}',
                 f'Triệu chứng: {c["symptom"]}', f'Nguyên nhân: {c["cause"]}', f'Cách sửa: {c["fix"]}']
        if c.get("specs"):
            lines.append(f"Thông số: {spec_text(c)}")
        if c.get("parts"):
            lines.append("Phụ tùng: " + ", ".join(c["parts"]))
        if c.get("tools"):
            lines.append("Dụng cụ: " + ", ".join(c["tools"]))
        if c.get("warnings"):
            lines.append("Lưu ý: " + "; ".join(c["warnings"]))
        parts.append("\n".join(lines))
    for i in chunk_idx:
        ch = st["chunks"][i]
        parts.append(f'[Đoạn video "{ch["title"]}", phút {dxa.mmss(ch["start"])}]\n{ch["text"]}')
    return "\n\n".join(parts)


SYSTEM = """Bạn là trợ lý của một thợ sửa xe máy, trả lời khách bằng tiếng Việt, giọng thợ nói chuyện dễ hiểu.
Quy tắc bắt buộc:
- CHỈ dùng thông tin trong NGỮ CẢNH. Không thêm kiến thức ngoài, không đoán.
- Giữ nguyên mọi con số và đơn vị như trong ngữ cảnh. Không đổi đơn vị, không tự tính ra số mới.
- Sau mỗi ý lấy từ một case, ghi mã case trong ngoặc vuông, ví dụ [C01] hoặc [T01] (T là case thợ nhập).
- Nếu NGỮ CẢNH không trả lời được câu hỏi, chỉ trả về đúng một dòng: KHONG_DU_THONG_TIN
- Không viết link, không viết phần nguồn: hệ thống tự gắn link video.
Cách trình bày: 1 câu nói bệnh gì và vì sao, rồi các bước sửa ngắn gọn, cuối cùng là thông số và lưu ý nếu có."""

PROMPT = """NGỮ CẢNH (trích từ video của thợ và kiến thức thợ nhập):
{ctx}

CÂU HỎI CỦA KHÁCH: {q}"""

NUM = re.compile(r"\d+(?:[.,]\d+)?")
LIST_MARK = re.compile(r"(?m)^\s*\d+[.)]\s")


def _numbers(text):
    out = set()
    for n in NUM.findall(text):
        n = n.replace(",", ".")
        out.add(n[:-2] if n.endswith(".0") else n)
    return out


def check_answer(text, ctx, q, allowed_ids):
    """Bộ kiểm 'bịa', giống tinh thần validate.py bước 3, áp cho câu trả lời của LLM."""
    problems = []
    bad_nums = _numbers(LIST_MARK.sub("", text)) - _numbers(ctx) - _numbers(q)
    if bad_nums:
        problems.append(f"con số không có trong nguồn: {sorted(bad_nums)}")
    cited = set(re.findall(r"\[([CT]\d+)\]", text))
    if cited - allowed_ids:
        problems.append(f"mã case không có trong ngữ cảnh: {sorted(cited - allowed_ids)}")
    if not cited:
        problems.append("không ghi mã case nào")
    return problems


def template_answer(st, case_idx):
    """Bản ghép khuôn, không cần LLM. Dùng khi offline hoặc khi câu của LLM không qua bộ kiểm."""
    c = st["cases"][case_idx[0]]
    lines = [f'Bệnh gần nhất: {c["symptom"]} [{c["id"]}]',
             f'Nguyên nhân: {c["cause"]}',
             f'Cách sửa: {c["fix"]}']
    if c.get("specs"):
        lines.append(f"Thông số: {spec_text(c)}")
    if c.get("warnings"):
        lines.append("Lưu ý: " + "; ".join(c["warnings"]))
    return "\n".join(lines)


def sources(st, case_idx, chunk_idx):
    out = []
    for i in case_idx:
        c = st["cases"][i]
        title, when, link = dxa.origin(st["videos"], c)
        out.append({"type": "case", "id": c["id"], "symptom": c["symptom"], "cause": c["cause"], "fix": c["fix"],
                    "specs": c.get("specs", []), "reviewed": bool(c.get("reviewed")),
                    "review_note": c.get("review_note"), "video_title": title, "time": when, "link": link,
                    "source": c.get("source", "video"), "author": c.get("author"), "created_at": c.get("created_at")})
    for i in chunk_idx:
        ch = st["chunks"][i]
        out.append({"type": "chunk", "id": ch["chunk_id"], "video_title": ch["title"], "time": dxa.mmss(ch["start"]),
                    "text": ch["text"], "link": chunk_link(ch)})
    return out


def log_unanswered(q, q2, reason):
    """Câu không trả lời được -> lưu lại cho thợ trả lời / gợi ý quay video mới."""
    rec = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "question": q, "query_used": q2, "reason": reason}
    with open(dxa.DATA / "unanswered.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


REFUSE = "Chưa có kiến thức này trong kho. Không đoán, cần thợ bổ sung kiến thức hoặc nạp thêm video."


def answer(q, use_llm=True):
    st = state()
    r = retrieve(q)
    out = {**r, "answer": None, "answered_by": None, "refused": False, "warnings": [], "sources": []}

    if not r["in_scope"] or not r["cases"]:
        log_unanswered(q, r["query_used"], "ngoài phạm vi")
        return {**out, "answer": REFUSE, "answered_by": "gate", "refused": True}

    ctx = build_context(st, r["cases"], r["chunks"])
    out["sources"] = sources(st, r["cases"], r["chunks"])

    if use_llm and G.available():
        try:
            text = G.generate(PROMPT.format(ctx=ctx, q=r["query_used"]), system=SYSTEM)
            if text.strip() == "KHONG_DU_THONG_TIN":
                log_unanswered(q, r["query_used"], "LLM: ngữ cảnh không đủ")
                return {**out, "answer": REFUSE, "answered_by": "llm", "refused": True}
            problems = check_answer(text, ctx, q, {st["cases"][i]["id"] for i in r["cases"]})
            if not problems:
                return {**out, "answer": text, "answered_by": "llm"}
            out["warnings"] += ["Câu của Gemini bị loại: " + p for p in problems]
        except Exception as e:
            out["warnings"].append(f"Gọi Gemini lỗi, dùng bản ghép khuôn: {e}")

    return {**out, "answer": template_answer(st, r["cases"]), "answered_by": "template"}


def render(res):
    """In ra màn hình cho người đọc."""
    lines = [res["answer"]]
    if res["query_used"] != res["question"]:
        lines.insert(0, f'(hiểu câu hỏi là: "{res["query_used"]}")')
    if not res["refused"]:
        lines += ["", "Xem video:"]
        for s in res["sources"]:
            tag = f'[{s["id"]}]' if s["type"] == "case" else "đoạn"
            lines.append(f'  {tag} {s["video_title"]} ({s["time"]}): {s["link"]}')
    for w in res["warnings"]:
        lines.append(f"! {w}")
    lines.append(f'[chế độ: {res["mode"]}, trả lời bởi: {res["answered_by"]}]')
    return "\n".join(lines)


if __name__ == "__main__":
    print(render(answer(" ".join(sys.argv[1:]))))
