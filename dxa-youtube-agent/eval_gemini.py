"""Chấm bản Gemini trên CÙNG bộ câu hỏi của eval.py, đặt cạnh bản offline để so.

    python eval_gemini.py          # chỉ chấm tìm kiếm (rẻ: mỗi câu 1 lần embed + 1 lần thêm dấu nếu không dấu)
    python eval_gemini.py --llm    # chấm thêm câu trả lời của LLM: bao nhiêu câu qua bộ kiểm "bịa"

Lưu ý: bộ câu hỏi này do người dựng hệ thống viết, điểm sẽ cao hơn thực tế.
"""
import sys

import eval as E
import gemini_client as G
import rag


def expected_set(exp):
    return {exp} if isinstance(exp, str) else set(exp)


def run(label):
    st = rag.state()
    ids = [c["id"] for c in st["cases"]]
    h1 = h3 = 0
    misses, noacc = [], [0, 0]
    for q, exp in E.QUESTIONS:
        r = rag.retrieve(q)
        got = [ids[i] for i in r["cases"]]
        want = expected_set(exp)
        ok1, ok3 = bool(got[:1]) and got[0] in want, bool(want & set(got[:3]))
        h1 += ok1
        h3 += ok3
        if not rag.has_accents(q):
            noacc[0] += ok1
            noacc[1] += 1
        if not ok1:
            misses.append(f"   {q!r}: cần {sorted(want)}, ra {got[:3]} (hiểu là {r['query_used']!r})")
    refused = sum(not rag.retrieve(q)["in_scope"] for q in E.OUT_OF_SCOPE)
    n = len(E.QUESTIONS)
    print(f"[{label}] Hit@1 {h1}/{n}  Hit@3 {h3}/{n}  câu không dấu Hit@1 {noacc[0]}/{noacc[1]}  "
          f"từ chối đúng {refused}/{len(E.OUT_OF_SCOPE)}")
    for m in misses:
        print(m)


def run_llm():
    passed = refused_wrong = 0
    fails = []
    for q, _ in E.QUESTIONS:
        res = rag.answer(q)
        if res["refused"]:
            refused_wrong += 1
            fails.append(f"   từ chối nhầm: {q!r}")
        elif res["answered_by"] == "llm":
            passed += 1
        else:
            fails.append(f"   {q!r}: {res['warnings']}")
    print(f"[LLM] qua bộ kiểm {passed}/{len(E.QUESTIONS)}, từ chối nhầm {refused_wrong}")
    for f in fails:
        print(f)


if __name__ == "__main__":
    rag.state()
    gemini_ready = rag._gemini_ok
    rag._gemini_ok = False
    run("offline TF-IDF")
    if gemini_ready:
        rag._gemini_ok = True
        run(f"Gemini {G.EMBED_MODEL}")
    else:
        print("Chưa chấm bản Gemini: cần GEMINI_API_KEY và đã chạy build_gemini.py")
    if "--llm" in sys.argv and G.available():
        run_llm()
