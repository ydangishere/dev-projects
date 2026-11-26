"""Standalone local telemetry smoke check, with an HTTP collector instead of Docker."""
import asyncio
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from tempfile import TemporaryDirectory
from pathlib import Path

payloads = []

class Collector(BaseHTTPRequestHandler):
    def do_POST(self):
        payloads.append(self.rfile.read(int(self.headers["Content-Length"])))
        self.send_response(200)
        self.end_headers()

server = ThreadingHTTPServer(("127.0.0.1", 0), Collector)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
os.environ.update(DXA_TRACE="1", LANGFUSE_PUBLIC_KEY="pk-lf-local-smoke",
                  LANGFUSE_SECRET_KEY="sk-lf-local-smoke",
                  LANGFUSE_BASE_URL=f"http://127.0.0.1:{server.server_port}")
from observability import client, instrument_dana, observe
from test_agentic import test_dialogue, test_loop_bound

with TemporaryDirectory() as folder:
    path = Path(folder) / "sessions.sqlite3"
    test_dialogue(path)
    test_loop_bound(path)

instrument_dana()
from dana.common.sys_resource.llm.llm_query_executor import LLMQueryExecutor

async def mock_query(_):
    return {"model": "smoke-model", "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10}}
async def run_generation_check():
    from types import SimpleNamespace
    with observe("smoke.parent"):
        await LLMQueryExecutor.query_once(SimpleNamespace(_mock_llm_call=mock_query), {})

asyncio.run(run_generation_check())
try:
    with observe("smoke.error"):
        raise LookupError("secret-smoke-payload")
except LookupError:
    pass
client().flush()
server.shutdown()
server.server_close()
raw = b"".join(payloads)
for span in ("dana.diagnose", "diagnostic.plan", "diagnostic.replan",
             "diagnostic.search_rag", "smoke.parent", "dana.reason",
             "smoke.error", "LookupError", "smoke-model", "usage_details"):
    assert span.encode() in raw, span
assert b"secret-smoke-payload" not in raw
print("Langfuse OTLP transport smoke passed")
