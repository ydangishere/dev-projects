import json
import time
import urllib.error
import urllib.request

base = "http://127.0.0.1:8000"
for attempt in range(30):
    try:
        with urllib.request.urlopen(base + "/healthz", timeout=2) as response:
            assert json.load(response)["status"] == "ok"
        break
    except (OSError, urllib.error.URLError):
        time.sleep(1)
else:
    raise SystemExit("Server failed readiness check")
request = urllib.request.Request(
    base + "/api/applications/APP-DEMO-001/checks",
    data=b"{}",
    headers={
        "Authorization": "Bearer demo-checker-token",
        "Content-Type": "application/json",
    },
)
with urllib.request.urlopen(request, timeout=10) as response:
    result = json.load(response)
assert {f["code"] for f in result["findings"]} == {
    "missing_document",
    "expired",
    "unverified_version",
}
assert result["approval"] == "human_decision_required"
print("HTTP smoke: health + authenticated full demo pipeline passed")
