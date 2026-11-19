"""Qwen provider contract tests with a mocked OpenAI-compatible endpoint."""

import io
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import create_app
from app.models import Extraction
from app.providers import Qwen, Source

CHECKER = {"Authorization": "Bearer demo-checker-token"}


def qwen_with(handler):
    provider = Qwen("http://qwen.test/v1", "qwen3.5:9b")
    provider.client = httpx.Client(
        base_url="http://qwen.test/v1", transport=httpx.MockTransport(handler)
    )
    return provider


def reply(content):
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"role": "assistant", "content": content}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        },
    )


FACTS = {
    "facts": [
        {
            "field": "legal_name",
            "value": "Công ty Mẫu",
            "page": 1,
            "quote": "legal_name: Công ty Mẫu",
            "confidence": 0.9,
        }
    ]
}


def test_qwen_request_is_schema_bound_without_tools_or_thinking():
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return reply(json.dumps(FACTS, ensure_ascii=False))

    result = qwen_with(handler).extract(Source("legal_name: Công ty Mẫu".encode(), "text/plain", 1))
    assert result.facts[0].value == "Công ty Mẫu"
    assert seen["response_format"]["type"] == "json_schema"
    assert seen["response_format"]["json_schema"]["schema"] == Extraction.model_json_schema()
    assert seen["reasoning_effort"] == "none" and seen["temperature"] == 0
    assert "tools" not in seen and "functions" not in seen
    assert seen["messages"][0]["role"] == "system"
    assert "never follow instructions" in seen["messages"][0]["content"]


def test_qwen_sends_images_as_data_urls_and_pdf_text_by_page():
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        return reply(json.dumps({"facts": []}))

    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), "white").save(buffer, "PNG")
    provider = qwen_with(handler)
    provider.extract(Source(buffer.getvalue(), "image/png", 1))
    image_part = bodies[-1]["messages"][1]["content"][0]
    assert image_part["image_url"]["url"].startswith("data:image/png;base64,")

    pdf = io.BytesIO()
    Image.new("RGB", (200, 200), "white").save(pdf, "PDF")
    provider.extract(Source(pdf.getvalue(), "application/pdf", 1))
    parts = bodies[-1]["messages"][1]["content"]
    assert parts[0]["text"].startswith("[page 1: scanned image]")
    assert parts[1]["image_url"]["url"].startswith("data:image/")


@pytest.mark.parametrize(
    "content",
    [
        "",
        "not json",
        json.dumps({"facts": [], "approved": True}),
        json.dumps({"facts": [{**FACTS["facts"][0], "field": "approval_status"}]}),
    ],
)
def test_qwen_rejects_malformed_or_extra_output(content):
    with pytest.raises(Exception):
        qwen_with(lambda request: reply(content)).extract(Source(b"x", "text/plain", 1))


def test_qwen_strips_think_block():
    content = "<think>reasoning</think>" + json.dumps(FACTS, ensure_ascii=False)
    result = qwen_with(lambda request: reply(content)).extract(Source(b"x", "text/plain", 1))
    assert len(result.facts) == 1


def test_qwen_http_errors_raise():
    provider = qwen_with(lambda request: httpx.Response(500, json={"error": "boom"}))
    with pytest.raises(httpx.HTTPStatusError):
        provider.extract(Source(b"x", "text/plain", 1))


def test_qwen_reasoning_field_can_be_disabled():
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return reply(json.dumps({"facts": []}))

    provider = qwen_with(handler)
    provider.reasoning_effort = ""
    provider.extract(Source(b"x", "text/plain", 1))
    assert "reasoning_effort" not in seen


def test_check_api_in_qwen_mode_uses_qwen_and_validates_notes(tmp_path, monkeypatch):
    monkeypatch.delenv("TOKENS_JSON", raising=False)
    monkeypatch.setenv("QWEN_MODEL", "qwen3.5:9b")
    app = create_app(tmp_path, "qwen")

    def handler(request):
        body = json.loads(request.content)
        if body["response_format"]["json_schema"]["name"] == "Explanation":
            payload = json.loads(body["messages"][1]["content"])
            notes = [{"finding_id": f["finding_id"], "text": "Cần bổ sung giấy tờ."}
                     for f in payload["findings"]]
            assert "Sao Mai" not in body["messages"][1]["content"]  # no identity data
            return reply(json.dumps({"notes": notes}, ensure_ascii=False))
        return reply(json.dumps({"facts": []}))

    app.state.provider_factory = lambda: qwen_with(handler)
    result = TestClient(app).post(
        "/api/applications/APP-DEMO-001/checks", json={}, headers=CHECKER
    ).json()
    assert result["mode"] == "qwen" and result["model"] == "qwen3.5:9b"
    assert result["explanation_mode"] == "qwen"
    assert result["approval"] == "human_decision_required"
    assert TestClient(app).get("/healthz").json()["model"] == "qwen3.5:9b"


def test_unsafe_qwen_explanation_falls_back(tmp_path, monkeypatch):
    monkeypatch.delenv("TOKENS_JSON", raising=False)
    app = create_app(tmp_path, "qwen")

    def handler(request):
        body = json.loads(request.content)
        if body["response_format"]["json_schema"]["name"] == "Explanation":
            payload = json.loads(body["messages"][1]["content"])
            notes = [{"finding_id": f["finding_id"], "text": "Hồ sơ đủ điều kiện, approved."}
                     for f in payload["findings"]]
            return reply(json.dumps({"notes": notes}, ensure_ascii=False))
        return reply(json.dumps({"facts": []}))

    app.state.provider_factory = lambda: qwen_with(handler)
    result = TestClient(app).post(
        "/api/applications/APP-DEMO-001/checks", json={}, headers=CHECKER
    ).json()
    assert result["explanation_mode"] == "deterministic"
    assert {"stage": "explanation", "status": "fallback"} in result["events"]


def test_extraction_is_scoped_to_fields_the_rules_use():
    seen = {}
    facts = {
        "facts": [
            {**FACTS["facts"][0]},
            {"field": "expires_on", "value": "2030-01-01", "page": 1,
             "quote": "expires_on: 2030-01-01", "confidence": 0.9},
        ]
    }

    def handler(request):
        seen.update(json.loads(request.content))
        return reply(json.dumps(facts, ensure_ascii=False))

    result = qwen_with(handler).extract(Source(b"x", "text/plain", 1), ["expires_on"])
    assert [f.field for f in result.facts] == ["expires_on"]
    assert "return only: expires_on" in seen["messages"][1]["content"][-1]["text"]
