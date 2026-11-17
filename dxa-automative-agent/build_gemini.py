"""Dựng tầng Vector bằng Gemini embedding, lưu vào Qdrant.

Chạy SAU `python dxa.py build` (cần index/state.pkl):
    python build_gemini.py

Văn bản đưa đi embed giống hệt cách dxa.py build làm cho tầng TF-IDF,
nên thứ tự chunk/case khớp với BM25, graph và SQL.
"""
import json
import time

import dxa
import gemini_client as G
from rag import load_state
from vector_store import VectorStore


def doc_texts(state):
    chunk_text = [c["title"] + ". " + c["text"] for c in state["chunks"]]
    case_text = [f'{c["symptom"]}. {c["cause"]}. {c["fix"]}. {" ".join(c.get("parts", []))}' for c in state["cases"]]
    return chunk_text, case_text


def main():
    if not G.available():
        raise SystemExit("Chưa có GEMINI_API_KEY. Đặt biến môi trường rồi chạy lại.")
    t0 = time.time()
    state = load_state()
    chunk_text, case_text = doc_texts(state)

    E_chunks = G.embed(chunk_text, task="RETRIEVAL_DOCUMENT")
    E_cases = G.embed(case_text, task="RETRIEVAL_DOCUMENT")

    store = VectorStore()
    store.put("chunks", E_chunks, [{"chunk_id": c["chunk_id"], "video_id": c["video_id"], "start": c["start"]} for c in state["chunks"]])
    store.put("cases", E_cases, [{"case_id": c["id"], "video_id": c["video_id"], "t": c["t"]} for c in state["cases"]])

    meta = {"embed_model": G.EMBED_MODEL, "dim": G.EMBED_DIM, "backend": store.backend,
            "chunks": len(chunk_text), "cases": len(case_text),
            "case_ids": [c["id"] for c in state["cases"]]}
    (dxa.OUT / "gemini_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Gemini vector: chunks={len(chunk_text)} cases={len(case_text)} dim={G.EMBED_DIM} "
          f"kho={store.backend} ({time.time() - t0:.1f}s)")


if __name__ == "__main__":
    main()
