"""Retrieval evaluation: Recall@K, Precision@K, MRR and NDCG@K on labeled questions.

Metrics are computed in pure Python so CI needs no extra packages. When the optional
`ranx` package is installed (requirements-eval.txt), the same runs are cross-checked
with ranx and both results are reported.

Questions have a `dev` split (used while building the retriever) and a `holdout` split
(written with different wording, not used to edit the rewrite vocabulary).
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from datetime import date
from pathlib import Path

from .observability import traced
from .rag import policy_bundle, retrieve
from .retrieval import HybridRetriever, RetrievalSettings

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "samples/retrieval_questions.json"
SPLITS = ("dev", "holdout", "all")


def recall_at(ranking, relevant, k):
    return len(set(ranking[:k]) & set(relevant)) / len(relevant)


def precision_at(ranking, relevant, k):
    return len(set(ranking[:k]) & set(relevant)) / k


def reciprocal_rank(ranking, relevant):
    for index, item in enumerate(ranking, start=1):
        if item in relevant:
            return 1.0 / index
    return 0.0


def ndcg_at(ranking, relevant: dict, k):
    def dcg(gains):
        return sum((2**g - 1) / math.log2(i + 2) for i, g in enumerate(gains))

    actual = dcg([relevant.get(item, 0) for item in ranking[:k]])
    ideal = dcg(sorted(relevant.values(), reverse=True)[:k])
    return actual / ideal if ideal else 0.0


def summarize(runs: dict, qrels: dict, k: int = 3, ndcg_k: int = 5):
    rows = {
        qid: {
            f"recall@{k}": recall_at(runs[qid], qrels[qid], k),
            f"precision@{k}": precision_at(runs[qid], qrels[qid], k),
            "mrr": reciprocal_rank(runs[qid], qrels[qid]),
            f"ndcg@{ndcg_k}": ndcg_at(runs[qid], qrels[qid], ndcg_k),
        }
        for qid in qrels
    }
    metrics = list(next(iter(rows.values())))
    mean = {m: round(sum(r[m] for r in rows.values()) / len(rows), 4) for m in metrics}
    return mean, rows


def load_questions(split: str = "all"):
    if split not in SPLITS:
        raise ValueError(f"split must be one of {SPLITS}")
    raw = QUESTIONS.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    questions = [q for q in data["questions"] if split == "all" or q["split"] == split]
    return data, questions, hashlib.sha256(raw).hexdigest()


def lexical_ranking(md, question, all_rules):
    ranked = [s["rule"] for s in retrieve(md, question, set())]
    return ranked + [r for r in sorted(all_rules) if r not in ranked]


def _ranx_check(qrels, runs_by_label, k, ndcg_k):
    try:
        from ranx import Qrels, Run, evaluate as ranx_evaluate
    except ImportError:
        return "ranx not installed; pure-Python metrics only"
    # ndcg_burges uses the same (2^rel - 1) gain as ndcg_at above.
    names = {
        f"recall@{k}": f"recall@{k}",
        f"precision@{k}": f"precision@{k}",
        "mrr": "mrr",
        f"ndcg_burges@{ndcg_k}": f"ndcg@{ndcg_k}",
    }
    rx_qrels = Qrels(qrels)
    return {
        label: {
            names[m]: round(float(v), 4)
            for m, v in ranx_evaluate(
                rx_qrels,
                Run({q: {r: len(rank) - i for i, r in enumerate(rank)} for q, rank in runs.items()}),
                list(names),
            ).items()
        }
        for label, runs in runs_by_label.items()
    }


@traced("retrieval_experiment")
def run_experiment(retriever: HybridRetriever, split: str = "all", k: int = 3, ndcg_k: int = 5):
    """Evaluate one retriever configuration; reused by scripts and the Chunking Lab."""
    data, questions, dataset_sha = load_questions(split)
    review = date.fromisoformat(data["review_date"])
    rules, md, policy_sha = policy_bundle(data["tenant"], review)
    all_rules = set(rules["rules"].values())
    qrels = {q["id"]: q["relevant"] for q in questions}
    started = time.perf_counter()
    lexical, hybrid, chunks = {}, {}, {}
    for q in questions:
        lexical[q["id"]] = lexical_ranking(md, q["text"], all_rules)
        sections, trace = retriever.search(
            md, rules, data["tenant"], data["review_date"], q["text"], all_rules
        )
        hybrid[q["id"]] = [s["rule"] for s in sections]
        chunks[q["id"]] = [c["chunk_id"] for c in trace["candidates"][:k]]
    elapsed = time.perf_counter() - started
    return {
        "split": split,
        "questions": len(qrels),
        "dataset_version": data.get("version"),
        "dataset_sha256": dataset_sha,
        "policy_sha256": policy_sha,
        "embedder": retriever.embedder.name,
        "settings": vars(retriever.settings),
        "lexical_baseline": summarize(lexical, qrels, k, ndcg_k)[0],
        "hybrid": summarize(hybrid, qrels, k, ndcg_k)[0],
        "ranx_cross_check": _ranx_check(
            qrels, {"lexical_baseline": lexical, "hybrid": hybrid}, k, ndcg_k
        ),
        "processing_seconds": round(elapsed, 3),
        "per_question": {
            qid: {
                "relevant": qrels[qid],
                "lexical": lexical[qid][:k],
                "hybrid": hybrid[qid][:k],
                "top_chunks": chunks[qid],
            }
            for qid in qrels
        },
    }


def run(k: int = 3, ndcg_k: int = 5, retriever: HybridRetriever | None = None):
    """Report dev and holdout splits for one retriever (default: local embeddings)."""
    retriever = retriever or HybridRetriever(settings=RetrievalSettings())
    return {split: run_experiment(retriever, split, k, ndcg_k) for split in ("dev", "holdout")}
