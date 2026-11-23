"""Real offline RAG latency regression: ten consecutive queries, no model calls.

Run after "python dxa.py build": python test_perf.py
Measures the loaded index and endpoint logic rather than mocking the retrieval engine.
"""
import os
import statistics
import time
from unittest.mock import patch

# Ensure the app is evaluated as offline, even when the runner has provider secrets.
os.environ.pop("GEMINI_API_KEY", None)
os.environ.pop("GOOGLE_API_KEY", None)

import api  # noqa: E402
import rag  # noqa: E402


QUESTIONS = [
    "Bình xăng con chảy xăng khi dựng xe",
    "buông ga mà ga không về",
    "Côn bị trượt",
    "Cò mổ bị bó, không có độ rơ",
    "binh xang con buong ga ma ga khong ve",
    "thay nhớt bao lâu một lần",
    "lốp xe bị xì",
    "chinh binh xang con mat ralenti",
    "Bình xăng con chảy xăng khi dựng xe",
    "Côn bị trượt",
]


def run():
    start = time.perf_counter()
    rag.state()
    rag.accent_dict()
    print(f"[DXA perf] warmup_ms={(time.perf_counter() - start) * 1000:.1f}")
    durations = []
    # An offline request must NEVER enter Dana, even when the user sent use_llm=true.
    with patch.object(api.G, "available", return_value=False):
        with patch.object(api.dxa_dana, "ask", side_effect=AssertionError("Offline must bypass Dana")):
            for i, question in enumerate(QUESTIONS, start=1):
                t0 = time.perf_counter()
                result = api.ask(api.AskIn(question=question, use_llm=True))
                duration = (time.perf_counter() - t0) * 1000
                durations.append(duration)
                assert result["answer"], f"Empty answer on iteration {i}"  # noqa: S101
                assert result["mode"] == "offline", (i, result["mode"])  # noqa: S101
                assert result["answered_by"] in ("gate", "template"), (i, result["answered_by"])  # noqa: S101
                assert result["timings_ms"]["retrieval_ms"] >= 0  # noqa: S101
                print(f"{i:02d}/10  {duration:.0f} ms  {result['answered_by']}  refused={result['refused']}")
    print(f"REAL OFFLINE RAG: 10/10 | p50={statistics.median(durations):.0f} ms "
          f"| max={max(durations):.0f} ms")
    # Time budget matches the front-end offline timeout (12 s); no silent 20-30 s hangs.
    assert max(durations) < 12000, f"Offline query exceeded 12s: {max(durations):.0f}ms"  # noqa: S101


if __name__ == "__main__":
    run()
