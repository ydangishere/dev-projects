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
import vn_text as V
from vector_store import VectorStore

TOP_CASES = 3
TOP_CHUNKS = 3
RRF_K = 60

_state = _store = None
_gemini_ok = False


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
    global _state, _store, _gemini_ok, _accent_dict
    _state, _store, _gemini_ok, _accent_dict = None, None, False, None


# ---------------------------------------------------------------- câu không dấu
def bare(s):
    """Bỏ dấu, chữ thường, chỉ giữ chữ và số: dùng để so 'có cùng chữ cái không'."""
    s = unicodedata.normalize("NFD", s.lower().replace("đ", "d").replace("Đ", "d"))
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]", "", s)


def has_accents(q):
    return any(unicodedata.category(ch) == "Mn" for ch in unicodedata.normalize("NFD", q)) or "đ" in q.lower()


TRANSLATE_PROMPT = """Câu dưới đây là câu hỏi tiếng Anh về sửa xe máy. Dịch sang tiếng Việt theo cách thợ sửa xe Việt Nam hay nói.
Thuật ngữ: carburetor = bình xăng con, idle = ralenti, rocker arm = cò mổ, camshaft = bánh cam, cam chain = sên cam,
valve = xupap, spark plug = bugi, float = phao xăng, relay = rơ le, turn signal = xi nhan, clutch = côn, frame = sườn.
Trả JSON: {{"query": "<câu tiếng Việt có dấu>"}}

Câu: {q}"""

accent_seconds = {}  # câu hỏi -> số giây chuẩn hóa câu hỏi (dịch bằng Gemini); api.py đọc để báo thời gian
_english = {}        # câu tiếng Việt đã dịch -> câu tiếng Anh gốc, để trả lời lại bằng tiếng Anh
_accent_dict = None
TRANSLATE_CACHE = dxa.OUT / "translate_cache.json"


def accent_dict():
    """Từ điển thêm dấu rút từ phụ đề, case và tên video trong kho (dựng một lần, ~0,1 giây)."""
    global _accent_dict
    if _accent_dict is None:
        st = state()
        texts = [ch["text"] for ch in st["chunks"]] + [v["title"] for v in st["videos"].values()]
        texts += [f'{c["symptom"]} {c["cause"]} {c["fix"]} {" ".join(c.get("parts", []))}' for c in st["cases"]]
        _accent_dict = V.AccentDict(texts)
    return _accent_dict


def _translate(q):
    cache = {}
    if TRANSLATE_CACHE.exists():
        try:
            cache = json.loads(TRANSLATE_CACHE.read_text(encoding="utf-8"))
        except ValueError:
            cache = {}
    if q not in cache:
        cand = str(G.generate(TRANSLATE_PROMPT.format(q=q), temperature=0, json_mode=True).get("query", "")).strip()
        if not cand:
            return q
        cache[q] = cand
        TRANSLATE_CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    return cache[q]


def restore_accents(q):
    """Chuẩn hóa câu hỏi:
    - có dấu: dùng luôn
    - không dấu: thêm dấu bằng từ điển rút từ video, KHÔNG gọi Gemini
    - tiếng Anh: gọi Gemini dịch sang tiếng Việt (một lần, có cache), rồi trả lời lại bằng tiếng Anh"""
    if has_accents(q):
        return q
    d = accent_dict()
    if V.looks_english(q, d):
        if not G.available():
            return q
        t0 = time.perf_counter()
        try:
            vi = _translate(q)
        except Exception as e:
            print(f"[rag] không dịch được: {e}", file=sys.stderr)
            vi = q
        accent_seconds[q] = time.perf_counter() - t0
        if vi != q:
            _english[vi] = q
        return vi
    return d.restore(q)


def is_english(query_used):
    return query_used in _english


EN_NOTE = "\nKhách hỏi bằng tiếng Anh: viết câu trả lời bằng tiếng Anh, vẫn ghi mã case trong ngoặc vuông."


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
    t0 = time.perf_counter()
    st = state()
    t_index = time.perf_counter()
    q2 = restore_accents(q)
    queries = [q] if q2 == q else [q, q2]
    t_normalize = time.perf_counter()

    case_bm, _ = _bm25_rank(st["bm25_cases"], queries)
    chunk_bm, _ = _bm25_rank(st["bm25_chunks"], queries)
    t_bm25 = time.perf_counter()
    case_vec = _vec_rank("cases", q2)
    chunk_vec = _vec_rank("chunks", q2)
    t_vector = time.perf_counter()
    cases = _rrf([case_bm, case_vec])[:top_cases]
    chunks = _rrf([chunk_bm, chunk_vec])[:top_chunks]
    levels = [dxa.scope_level(st, x) for x in queries]
    t_done = time.perf_counter()

    return {
        "question": q,
        "query_used": q2,
        "in_scope": "in" in levels,
        "near": "in" not in levels and "near" in levels,
        "cases": [i for i, _ in cases],
        "chunks": [i for i, _ in chunks],
        "mode": mode(),
        "timings_ms": {
            "index_ms": round((t_index - t0) * 1000, 2),
            "normalize_ms": round((t_normalize - t_index) * 1000, 2),
            "bm25_ms": round((t_bm25 - t_normalize) * 1000, 2),
            "vector_ms": round((t_vector - t_bm25) * 1000, 2),
            "rank_gate_ms": round((t_done - t_vector) * 1000, 2),
            "retrieval_ms": round((t_done - t0) * 1000, 2),
        },
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


REFUSE = "Tôi đã tìm trong kho kiến thức DXA nhưng chưa thấy tài liệu đủ phù hợp để trả lời chắc chắn. Câu hỏi đã được ghi nhận để thợ xem xét bổ sung kiến thức."
NEAR_NOTE = "Câu hỏi chưa khớp hẳn với kiến thức trong kho, đây là câu trả lời gần nhất. Câu hỏi đã được lưu để thợ bổ sung."


def answer(q, use_llm=True):
    st = state()
    r = retrieve(q)
    out = {**r, "answer": None, "answered_by": None, "refused": False, "warnings": [], "sources": []}

    # Quy tắc: có nguồn (video) thì phải có câu trả lời bằng chữ; từ chối thì không kèm nguồn.
    if not r["cases"] or not (r["in_scope"] or r["near"]):
        log_unanswered(q, r["query_used"], "ngoài phạm vi")
        return {**out, "answer": REFUSE, "answered_by": "gate", "refused": True, "near": False}
    if r["near"]:
        log_unanswered(q, r["query_used"], "gần đúng")

    ctx = build_context(st, r["cases"], r["chunks"])
    out["sources"] = sources(st, r["cases"], r["chunks"])

    if use_llm and G.available():
        try:
            text = G.generate(PROMPT.format(ctx=ctx, q=r["query_used"]) + (EN_NOTE if is_english(r["query_used"]) else ""), system=SYSTEM)
            if text.strip() == "KHONG_DU_THONG_TIN":
                log_unanswered(q, r["query_used"], "LLM: ngữ cảnh không đủ")
                return {**out, "answer": REFUSE, "answered_by": "llm", "refused": True, "near": False, "sources": []}
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
