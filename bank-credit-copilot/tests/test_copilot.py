from __future__ import annotations

import json
from datetime import date

import pytest

from app import extraction as extraction_module
from app import memo as memo_module
from app.documents import load_document
from app.extraction import extract
from app.llm import LLMConfig
from app.pipeline import SAMPLE_AS_OF, CreditCopilot, Settings
from app.rules import annuity_payment, evaluate
from app.textutil import mask_id, norm, parse_vnd

FAKE_LLM = LLMConfig(provider="openai", model="test", api_key="x", base_url="http://localhost:1/v1")


@pytest.fixture()
def copilot(tmp_path):
    settings = Settings()
    settings.audit_path = tmp_path / "audit.jsonl"
    return CreditCopilot(settings, LLMConfig())


@pytest.mark.parametrize("case_id, verdict", [
    ("HS-001", "APPROVE"), ("HS-002", "REJECT"), ("HS-003", "NEED_INFO"), ("HS-004", "REJECT"),
])
def test_sample_verdicts(copilot, case_id, verdict):
    result = copilot.assess_sample(case_id)
    assert result["verdict"] == verdict
    assert result["as_of"] == SAMPLE_AS_OF.isoformat()
    assert all(r["clause_text"] for r in result["rules"]), "every rule must cite an existing clause"


def test_extraction_keeps_source_of_each_value(copilot):
    result = copilot.assess_sample("HS-001")
    name = result["extraction"]["fields"]["cccd"]["full_name"]
    assert name["value"] == "Nguyễn Văn An"
    assert name["filename"] == "01_cccd.pdf" and name["page"] == 1
    assert "Họ và tên" in name["raw"]
    assert [c["amount"] for c in result["extraction"]["salary_credits"]] == [24_800_000, 25_000_000, 25_000_000]


def test_income_uses_lower_of_contract_and_statement(copilot):
    facts = copilot.assess_sample("HS-001")["facts"]
    assert facts["contract_salary"] == 25_000_000
    assert facts["income_for_assessment"] == 24_933_333


def test_dti_failure_is_explained(copilot):
    dti_rule = next(r for r in copilot.assess_sample("HS-002")["rules"] if r["rule_id"] == "R10")
    assert dti_rule["status"] == "FAIL"
    assert "57.3%" in dti_rule["detail"]


def test_mismatched_id_asks_for_verification(copilot):
    rule = next(r for r in copilot.assess_sample("HS-003")["rules"] if r["rule_id"] == "R04")
    assert rule["status"] == "NEED_INFO"
    assert "...083" in rule["detail"] and "079095000083" not in rule["detail"]


def test_missing_documents_need_info(copilot):
    files = [f for f in copilot.sample_files("HS-001") if "sao_ke" not in f[0]]
    result = copilot.assess_files(files, as_of=SAMPLE_AS_OF)
    statuses = {r["rule_id"]: r["status"] for r in result["rules"]}
    assert statuses["R01"] == "NEED_INFO"
    assert result["verdict"] == "NEED_INFO"


def test_text_upload_and_unknown_file(copilot):
    text = ("GIẤY ĐỀ NGHỊ VAY VỐN\nHọ và tên khách hàng: Test\nSố tiền đề nghị vay: 10.000.000 VND\n"
            "Thời hạn vay: 12 tháng").encode()
    result = copilot.assess_files([("don.txt", text), ("anh.png", b"\x89PNG")], as_of=SAMPLE_AS_OF)
    assert result["extraction"]["fields"]["loan_application"]["requested_amount"]["value"] == 10_000_000
    assert any("anh.png" in w for w in result["extraction"]["warnings"])


def test_audit_masks_identifiers(copilot):
    copilot.assess_sample("HS-001")
    raw = copilot.settings.audit_path.read_text(encoding="utf-8")
    assert "079090000001" not in raw
    assert json.loads(raw.splitlines()[-1])["applicant_id"] == "*********001"


def test_policy_answers_with_citation_and_refuses_off_topic(copilot):
    answer = copilot.ask_policy("DTI tối đa là bao nhiêu?")
    assert answer["cited"] == ["5.3"] and "50%" in answer["answer"]
    refusal = copilot.ask_policy("Giá vàng hôm nay")
    assert refusal["cited"] == [] and refusal["source"] == "refusal"


def test_llm_narrative_with_invented_number_falls_back(copilot, monkeypatch):
    monkeypatch.setattr(memo_module, "complete_json", lambda *a, **k: {
        "summary": "Khách hàng có thu nhập 99.000.000 VND, rất tốt.", "risks": [], "follow_ups": []})
    copilot.llm = FAKE_LLM
    narrative = copilot.assess_sample("HS-001")["narrative"]
    assert narrative["source"] == "template"
    assert "99000000" in narrative["fallback_reason"]


def test_llm_narrative_with_grounded_numbers_is_used(copilot, monkeypatch):
    monkeypatch.setattr(memo_module, "complete_json", lambda *a, **k: {
        "summary": "Khoản vay 120.000.000 VND, DTI 24.5%, đạt toàn bộ điều kiện.", "risks": [], "follow_ups": []})
    copilot.llm = FAKE_LLM
    assert copilot.assess_sample("HS-001")["narrative"]["source"] == "openai"


def test_llm_extraction_drops_fabricated_quotes(monkeypatch):
    doc = load_document("don.txt", "GIẤY ĐỀ NGHỊ VAY VỐN\nKhách hàng: Test\nVay 50 triệu trong 1 năm".encode())
    monkeypatch.setattr(extraction_module, "complete_json", lambda *a, **k: {
        "requested_amount": {"value": "80.000.000", "quote": "Số tiền đề nghị vay: 80.000.000 VND"},
        "purpose": {"value": "Học phí", "quote": "Vay 50 triệu trong 1 năm"},
    })
    result = extract([doc], FAKE_LLM, send_documents_to_llm=True)
    fields = result.fields["loan_application"]
    assert "requested_amount" not in fields  # quote does not exist in the document
    assert fields["purpose"].method == "llm"


def test_documents_not_sent_to_llm_unless_allowed(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("document text must not be sent")
    monkeypatch.setattr(extraction_module, "complete_json", boom)
    doc = load_document("don.txt", "GIẤY ĐỀ NGHỊ VAY VỐN\nKhách hàng: Test".encode())
    extract([doc], FAKE_LLM, send_documents_to_llm=False)


def test_helpers():
    assert parse_vnd("+24.800.000") == 24_800_000
    assert norm("Nguyễn  Văn ĐAN") == "nguyen van dan"
    assert mask_id("0011 2233 4401") == "*********401"
    assert round(annuity_payment(120_000_000, 36)) == 4_101_316


def test_rules_handle_empty_extraction():
    facts, results, verdict = evaluate(extract([]), date(2026, 11, 26))
    assert verdict == "NEED_INFO"
    assert {r.status for r in results} == {"NEED_INFO"}
    assert facts.dti is None
