"""In-process Prometheus metrics (text exposition format 0.0.4), no extra package.

Labels are bounded: route templates (not raw paths), status codes, fixed stage and
finding codes. No user, tenant, application ID, document content or question is used
as a label. Counters reset when the process restarts; scrape them into Prometheus or
another collector for history and alerts.
"""

from __future__ import annotations

import threading
import time

BUCKETS = (0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60)


def _escape(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _labels(labels: dict) -> str:
    if not labels:
        return ""
    return "{" + ",".join(f'{k}="{_escape(v)}"' for k, v in sorted(labels.items())) + "}"


class Metrics:
    def __init__(self):
        self.lock = threading.Lock()
        self.counters: dict[tuple[str, tuple], float] = {}
        self.histograms: dict[tuple[str, tuple], list] = {}
        self.help = {
            "mms_http_requests_total": ("counter", "HTTP requests by route template, method and status"),
            "mms_http_request_seconds": ("histogram", "HTTP request latency by route template"),
            "mms_checks_total": ("counter", "Completed document checks by AI mode"),
            "mms_findings_total": ("counter", "Rule Engine findings by code"),
            "mms_check_events_total": ("counter", "Check pipeline events by stage and status"),
            "mms_uploads_rejected_total": ("counter", "Rejected uploads by reason"),
            "mms_model_seconds": ("histogram", "Document check processing time by AI mode"),
            "mms_investigations_total": ("counter", "Transaction investigations by outcome"),
        }

    def inc(self, name: str, value: float = 1, **labels):
        key = (name, tuple(sorted(labels.items())))
        with self.lock:
            self.counters[key] = self.counters.get(key, 0) + value

    def observe(self, name: str, seconds: float, **labels):
        key = (name, tuple(sorted(labels.items())))
        with self.lock:
            buckets = self.histograms.setdefault(key, [0] * len(BUCKETS) + [0, 0.0])
            for i, bound in enumerate(BUCKETS):
                if seconds <= bound:
                    buckets[i] += 1
            buckets[-2] += 1
            buckets[-1] += seconds

    def render(self) -> str:
        lines = []
        with self.lock:
            counters, histograms = dict(self.counters), {k: list(v) for k, v in self.histograms.items()}
        for name, (kind, text) in self.help.items():
            lines += [f"# HELP {name} {text}", f"# TYPE {name} {kind}"]
            if kind == "counter":
                for (metric, labels), value in sorted(counters.items()):
                    if metric == name:
                        lines.append(f"{name}{_labels(dict(labels))} {value:g}")
            else:
                for (metric, labels), values in sorted(histograms.items()):
                    if metric != name:
                        continue
                    base = dict(labels)
                    for bound, count in zip(BUCKETS, values):
                        lines.append(f"{name}_bucket{_labels({**base, 'le': f'{bound:g}'})} {count}")
                    lines.append(f"{name}_bucket{_labels({**base, 'le': '+Inf'})} {values[-2]}")
                    lines.append(f"{name}_count{_labels(base)} {values[-2]}")
                    lines.append(f"{name}_sum{_labels(base)} {values[-1]:.6f}")
        return "\n".join(lines) + "\n"


class MetricsMiddleware:
    """Counts requests by matched route template after routing has happened."""

    def __init__(self, app, metrics: Metrics):
        self.app, self.metrics = app, metrics

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        start, status = time.perf_counter(), {"code": 500}

        async def capture(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, capture)
        finally:
            route = scope.get("route")
            template = getattr(route, "path", None) or "unmatched"
            self.metrics.inc(
                "mms_http_requests_total",
                route=template,
                method=scope.get("method", ""),
                status=str(status["code"]),
            )
            self.metrics.observe("mms_http_request_seconds", time.perf_counter() - start, route=template)
