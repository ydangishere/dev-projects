"""Tracing (Langfuse) and metrics (Prometheus), both optional.

* Langfuse: enabled when LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are set
  (LANGFUSE_HOST points at Langfuse Cloud or a self-hosted server). Every pipeline step
  and every LLM call becomes a span, so a reviewer can replay what the model saw and said.
* Prometheus: counters and histograms exposed on /metrics when prometheus-client is
  installed. Grafana dashboards read from there.

If a library is missing the helpers become no-ops, so the core demo still runs offline.
"""

from __future__ import annotations

import os
from contextlib import contextmanager

try:  # pragma: no cover - import guard
    from langfuse import get_client as _lf_get_client
    from langfuse import observe as _lf_observe
except Exception:  # noqa: BLE001 - any import problem disables tracing
    _lf_get_client = None
    _lf_observe = None

try:  # pragma: no cover - import guard
    from prometheus_client import Counter, Histogram
except Exception:  # noqa: BLE001
    Counter = Histogram = None


def langfuse_enabled() -> bool:
    return bool(_lf_observe and os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))


def traced(name: str, as_type: str = "span"):
    """Decorator: a Langfuse span/generation when tracing is on, otherwise the function itself."""

    def wrap(func):
        if not langfuse_enabled():
            return func
        return _lf_observe(name=name, as_type=as_type)(func)

    return wrap


def flush_traces() -> None:
    if langfuse_enabled() and _lf_get_client:
        try:
            _lf_get_client().flush()
        except Exception:  # noqa: BLE001 - tracing must never break the request
            pass


class _NoopMetric:
    def labels(self, *args, **kwargs):
        return self

    def inc(self, amount: float = 1) -> None:
        pass

    def observe(self, value: float) -> None:
        pass


def _counter(name: str, doc: str, labels: list[str]):
    return Counter(name, doc, labels) if Counter else _NoopMetric()


def _histogram(name: str, doc: str, labels: list[str], buckets: tuple):
    return Histogram(name, doc, labels, buckets=buckets) if Histogram else _NoopMetric()


ASSESSMENTS = _counter("copilot_assessments_total", "Credit assessments by verdict", ["verdict"])
ASSESSMENT_SECONDS = _histogram("copilot_assessment_seconds", "End-to-end assessment latency", [],
                                (0.1, 0.5, 1, 2, 5, 10, 20, 40, 80))
LLM_CALLS = _counter("copilot_llm_calls_total", "LLM calls by purpose and outcome", ["purpose", "outcome"])
LLM_SECONDS = _histogram("copilot_llm_seconds", "LLM call latency", ["purpose"],
                         (0.25, 0.5, 1, 2, 4, 8, 16, 32, 64))
LLM_TOKENS = _counter("copilot_llm_tokens_total", "Tokens used by LLM calls", ["purpose", "kind"])
FALLBACKS = _counter("copilot_llm_fallbacks_total", "LLM output rejected and replaced by deterministic output",
                     ["purpose", "reason"])
GUARD_EVENTS = _counter("copilot_guard_events_total", "Guardrail decisions", ["stage", "result"])
PII_MASKED = _counter("copilot_pii_masked_total", "PII entities masked before leaving the service", ["entity"])
POLICY_QUESTIONS = _counter("copilot_policy_questions_total", "Policy questions by outcome", ["outcome"])


@contextmanager
def timer(histogram, **labels):
    import time

    start = time.perf_counter()
    try:
        yield
    finally:
        metric = histogram.labels(**labels) if labels else histogram
        metric.observe(time.perf_counter() - start)
