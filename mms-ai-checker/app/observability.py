"""Optional LangSmith tracing for retrieval and evaluation steps.

Off by default. Enabled only when LANGSMITH_TRACING=true, LANGSMITH_API_KEY is set and
the `langsmith` package is installed (requirements-observability.txt). Otherwise the
decorator returns the function unchanged, so the app never depends on LangSmith.

Privacy: traced inputs are reduced to non-sensitive fields (question, tenant, review
date, settings). Full policy text, application data and documents are not sent. Traced
outputs keep rule IDs, scores and chunk IDs, not policy text.
"""

from __future__ import annotations

import os

SAFE_INPUT_KEYS = {"query", "tenant", "review_date", "split", "required_rule_ids"}


def enabled() -> bool:
    return (
        os.getenv("LANGSMITH_TRACING", "").casefold() == "true"
        and bool(os.getenv("LANGSMITH_API_KEY"))
    )


def _inputs(inputs: dict) -> dict:
    slim = {k: v for k, v in inputs.items() if k in SAFE_INPUT_KEYS}
    if "required_rule_ids" in slim:
        slim["required_rule_ids"] = sorted(slim["required_rule_ids"])
    retriever = inputs.get("self") or inputs.get("retriever")
    settings = getattr(retriever, "settings", None)
    if settings is not None:
        slim["settings"] = vars(settings)
        slim["embedder"] = retriever.embedder.name
    return slim


def _outputs(output) -> dict:
    if isinstance(output, tuple) and len(output) == 2:
        sections, trace = output
        return {
            "sections": [
                {"rule": s["rule"], "score": s["score"], "chunk_ids": s.get("chunk_ids", [])}
                for s in sections
            ],
            "status": trace.get("status"),
            "embedder": trace.get("embedder"),
            "subqueries": trace.get("subqueries"),
        }
    if isinstance(output, dict) and "hybrid" in output:
        return {k: output[k] for k in ("lexical_baseline", "hybrid", "questions", "embedder")}
    return {"type": type(output).__name__}


def traced(name: str, run_type: str = "chain"):
    def decorate(func):
        if not enabled():
            return func
        try:
            from langsmith import traceable
        except ImportError:
            return func
        return traceable(
            name=name,
            run_type=run_type,
            process_inputs=_inputs,
            process_outputs=_outputs,
        )(func)

    return decorate
