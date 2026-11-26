"""HTTP-level tests. Skipped automatically when FastAPI is not installed."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from app import main  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main.copilot.audit, "path", tmp_path / "audit.jsonl")
    return TestClient(main.app)


def test_health_and_index(client):
    assert client.get("/health").json()["status"] == "ok"
    assert "Credit Copilot" in client.get("/").text


def test_assess_sample_and_audit(client):
    body = client.post("/api/assess/sample/HS-002").json()
    assert body["verdict"] == "REJECT"
    assert client.get("/api/audit").json()[0]["case_id"] == "HS-002"
    assert client.post("/api/assess/sample/HS-999").status_code == 404


def test_upload(client):
    files = [("files", (p.name, p.read_bytes(), "application/pdf"))
             for p in sorted((main.copilot.settings.samples_dir / "hs-001").glob("*.pdf"))]
    assert client.post("/api/assess", files=files).json()["applicant"] == "Nguyễn Văn An"


def test_policy_and_sample_file_guard(client):
    answer = client.post("/api/policy/ask", json={"question": "Sao kê lương cần mấy tháng?"}).json()
    assert answer["cited"] == ["4.2"]
    assert client.get("/samples/hs-001/01_cccd.pdf").status_code == 200
    assert client.get("/samples/..%2F..%2Fapp/main.py").status_code == 404


def test_health_reports_components_and_metrics(client):
    health = client.get("/health").json()
    assert health["provider"] == "offline" and health["tracing"] == "off"
    assert health["pii"]["engine"] in {"presidio", "regex-fallback"}
    client.post("/api/assess/sample/HS-001")
    metrics = client.get("/metrics/").text
    assert "copilot_assessments_total" in metrics
