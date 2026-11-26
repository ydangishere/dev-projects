"""Build a provenance-labelled dataset and run Dana's offline baseline."""
import argparse
import json
import os
import statistics
import time
from collections import Counter
from pathlib import Path

from eval import NO_ACCENT, OUT_OF_SCOPE, QUESTIONS


def dataset(state):
    indexed = {case["id"]: case for case in state["cases"]}
    rows = []

    def format_fix(value):
        return "\n".join(value) if isinstance(value, list) else (value or "")

    def add(question, ids, provenance, status, task):
        references = [indexed[case_id] for case_id in sorted(ids)]
        expected = "\n".join(
            f'{c["id"]}: {c["symptom"]}\n{c.get("cause", "")}\n' +
            format_fix(c.get("fix")) for c in references
        )
        rows.append(dict(id=f"DXA-{len(rows)+1:03}", question=question,
                         expected_ids=sorted(ids), expected_answer=expected,
                         status=status, task=task, provenance=provenance))

    for group, questions in (("QUESTIONS", QUESTIONS), ("NO_ACCENT", NO_ACCENT)):
        for question, ids in questions:
            add(question, ids, "eval.py:" + group, "verified_repo_label", "answer")
    for question in OUT_OF_SCOPE:
        add(question, (), "eval.py:OUT_OF_SCOPE", "verified_repo_label", "refuse")

    seen = {row["question"].casefold() for row in rows}
    for case in state["cases"]:
        if len(rows) == 100:
            break
        question = f'Trường hợp “{case["symptom"]}” trong kho DXA thì nên kiểm tra và xử lý thế nào?'
        if question.casefold() not in seen:
            add(question, [case["id"]], f'index/state.pkl:{case["id"]}',
                "unverified_prompt", "answer")
            seen.add(question.casefold())
    if len(rows) != 100:
        raise ValueError(f"Need 100 distinct prompts, got {len(rows)}")
    return rows


def semantic_metrics(model_name):
    from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric, GEval
    from deepeval.models import OllamaModel
    from deepeval.test_case import LLMTestCaseParams as Params

    judge = OllamaModel(model=model_name, base_url="http://127.0.0.1:11434")
    return {
        "correctness": GEval(name="Correctness", model=judge,
            criteria="Compare the answer to the source reference. Penalize unsupported or contradictory repair facts.",
            evaluation_params=[Params.INPUT, Params.ACTUAL_OUTPUT, Params.EXPECTED_OUTPUT],
            async_mode=False),
        "faithfulness": FaithfulnessMetric(model=judge, async_mode=False),
        "relevance": AnswerRelevancyMetric(model=judge, async_mode=False),
    }


def run(questions, judge=None, judge_limit=None):
    for key in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "LOCAL_API_KEY", "DANA_MOCK_LLM"):
        os.environ[key] = ""
    os.environ["DANA_CONFIG"] = str(Path("index/dana_config.json").resolve())
    os.environ["DEEPEVAL_TELEMETRY_OPT_OUT"] = "YES"
    import dxa_dana
    import rag
    import dxa_tools

    # Baseline questions should never populate the mechanic's feedback queue.
    dxa_tools.log_unanswered = lambda *args: True
    rag.log_unanswered = lambda *args: None
    metrics = semantic_metrics(judge) if judge else {}
    results = []
    judged = 0
    for case in questions:
        started = time.perf_counter()
        result = dxa_dana.ask(case["question"])
        elapsed = round((time.perf_counter() - started) * 1000, 3)
        evidence = dxa_tools.retrieve(case["question"])
        got = evidence["case_ids"][:3]
        gold = set(case["expected_ids"])
        hit1 = bool(gold.intersection(got[:1])) if gold else None
        hit3 = bool(gold.intersection(got)) if gold else None
        recall = len(gold.intersection(got)) / len(gold) if gold else None
        source_ids = {s["id"] for s in result["sources"] if s["type"] == "case"}
        success = (result["refused"] and not result["sources"] if case["task"] == "refuse"
                   else not result["refused"] and bool(result["answer"]) and bool(gold & source_ids))
        scores = {}
        errors = {}
        if metrics and case["status"] == "verified_repo_label" and gold and not result["refused"] and (judge_limit is None or judged < judge_limit):
            judged += 1
            from deepeval.test_case import LLMTestCase
            sample = LLMTestCase(input=case["question"], actual_output=result["answer"],
                                 expected_output=case["expected_answer"],
                                 retrieval_context=[evidence["context"]])
            for key, metric in metrics.items():
                try:
                    metric.measure(sample)
                    scores[key] = metric.score
                except Exception as error:
                    errors[key] = type(error).__name__
        results.append(dict(id=case["id"], status=case["status"], task=case["task"],
                            mode=result["mode"], answered_by=result["answered_by"],
                            latency_ms=elapsed, retrieved_ids=got, hit1=hit1, hit3=hit3,
                            recall_at_3=recall, task_success_proxy=success,
                            warning_count=len(result["warnings"]), scores=scores, errors=errors))
    return results


def summarize(results):
    summary = {}
    for status in sorted({row["status"] for row in results}):
        rows = [row for row in results if row["status"] == status]
        latency = sorted(row["latency_ms"] for row in rows)
        ranked = [row for row in rows if row["hit3"] is not None]
        summary[status] = dict(
            cases=len(rows), hit1=[sum(r["hit1"] for r in ranked), len(ranked)],
            hit3=[sum(r["hit3"] for r in ranked), len(ranked)],
            mean_recall_at_3=statistics.mean(r["recall_at_3"] for r in ranked),
            task_success_proxy=[sum(r["task_success_proxy"] for r in rows), len(rows)],
            refusal_success=[sum(r["task_success_proxy"] for r in rows if r["task"] == "refuse"),
                             sum(r["task"] == "refuse" for r in rows)],
            latency_p50_ms=statistics.median(latency),
            latency_p95_ms=statistics.quantiles(latency, n=100, method="inclusive")[94],
            modes=dict(Counter(r["mode"] for r in rows)),
            answer_paths=dict(Counter(r["answered_by"] for r in rows)),
            cases_with_warnings=sum(bool(r["warning_count"]) for r in rows),
        )
        for metric in ("correctness", "faithfulness", "relevance"):
            scores = [r["scores"][metric] for r in rows if metric in r["scores"]]
            summary[status][metric] = dict(mean=statistics.mean(scores) if scores else None,
                                           scored=len(scores))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("docs/day1-cases.json"))
    parser.add_argument("--output", type=Path, default=Path("day1-baseline.json"))
    parser.add_argument("--rebuild-dataset", action="store_true")
    parser.add_argument("--judge", help="Optional existing local Ollama model name")
    parser.add_argument("--judge-limit", type=int, help="Limit semantic evaluation for a smoke test")
    args = parser.parse_args()
    if args.rebuild_dataset:
        import rag
        args.dataset.write_text(json.dumps(dataset(rag.load_state()), ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")
    questions = json.loads(args.dataset.read_text(encoding="utf-8"))
    if len(questions) != 100 or len({q["question"] for q in questions}) != 100:
        parser.error("Expected 100 distinct questions")
    results = run(questions, args.judge, args.judge_limit)
    summary = summarize(results)
    args.output.write_text(json.dumps({"judge": args.judge, "summary": summary, "results": results},
                                      ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
