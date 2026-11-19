"""Retrieval evaluation: Recall@K, Precision@K, MRR and NDCG@K on labeled questions.

Metrics are computed in pure Python so CI needs no extra packages. When the optional
`ranx` package is installed (requirements-eval.txt), the same runs are cross-checked
with ranx and both results are reported.
"""

from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path

from .rag import policy_bundle, retrieve
from .retrieval import HybridRetriever

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "samples/retrieval_questions.json"


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


def _lexical_ranking(md, question, all_rules):
    ranked = [s["rule"] for s in retrieve(md, question, set())]
    return ranked + [r for r in sorted(all_rules) if r not in ranked]


def run(k: int = 3, ndcg_k: int = 5, retriever: HybridRetriever | None = None):
    data = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    review = date.fromisoformat(data["review_date"])
    rules, md, digest = policy_bundle(data["tenant"], review)
    all_rules = set(rules["rules"].values())
    retriever = retriever or HybridRetriever()
    qrels = {q["id"]: q["relevant"] for q in data["questions"]}
    lexical, hybrid = {}, {}
    for q in data["questions"]:
        lexical[q["id"]] = _lexical_ranking(md, q["text"], all_rules)
        sections, _ = retriever.search(
            md, rules, data["tenant"], data["review_date"], q["text"], all_rules
        )
        hybrid[q["id"]] = [s["rule"] for s in sections]
    report = {
        "scope": data["scope"],
        "policy_sha256": digest,
        "questions": len(qrels),
        "embedder": retriever.embedder.name,
        "settings": vars(retriever.settings),
        "lexical_baseline": summarize(lexical, qrels, k, ndcg_k)[0],
        "hybrid": summarize(hybrid, qrels, k, ndcg_k)[0],
        "per_question": {
            qid: {"relevant": qrels[qid], "lexical": lexical[qid][:k], "hybrid": hybrid[qid][:k]}
            for qid in qrels
        },
    }
    try:
        from ranx import Qrels, Run, evaluate as ranx_evaluate
    except ImportError:
        report["ranx_cross_check"] = "ranx not installed; pure-Python metrics only"
    else:
        # ndcg_burges uses the same (2^rel - 1) gain as ndcg_at above.
        names = {
            f"recall@{k}": f"recall@{k}",
            f"precision@{k}": f"precision@{k}",
            "mrr": "mrr",
            f"ndcg_burges@{ndcg_k}": f"ndcg@{ndcg_k}",
        }
        rx_qrels = Qrels(qrels)
        report["ranx_cross_check"] = {
            label: {
                names[m]: round(float(v), 4)
                for m, v in ranx_evaluate(
                    rx_qrels,
                    Run({q: {r: len(rank) - i for i, r in enumerate(rank)} for q, rank in runs.items()}),
                    list(names),
                ).items()
            }
            for label, runs in (("lexical_baseline", lexical), ("hybrid", hybrid))
        }
    return report
