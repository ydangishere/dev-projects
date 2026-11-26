"""End-to-end flow: documents → extraction → rules → memo → audit, plus policy Q&A."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .audit import AuditLog
from .documents import Document, DocumentError, load_document
from .extraction import extract
from .llm import LLMConfig, LLMError, complete_json
from .memo import llm_narrative, numbers_in
from .policy import PolicyIndex
from .rules import VERDICTS, evaluate
from .textutil import mask_id, today

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_AS_OF = date(2026, 11, 26)  # the synthetic documents are dated relative to this day
MIN_POLICY_SCORE = 1.0
MIN_QUERY_COVERAGE = 0.5


@dataclass
class Settings:
    policy_path: Path = ROOT / "policies" / "consumer_loan_policy.md"
    samples_dir: Path = ROOT / "samples"
    audit_path: Path = ROOT / "data" / "audit.jsonl"
    send_documents_to_llm: bool = False

    @classmethod
    def from_env(cls) -> Settings:
        settings = cls()
        if os.getenv("AUDIT_PATH"):
            settings.audit_path = Path(os.environ["AUDIT_PATH"])
        settings.send_documents_to_llm = os.getenv("LLM_SEND_DOCUMENTS", "false").lower() == "true"
        return settings


class CreditCopilot:
    def __init__(self, settings: Settings | None = None, llm: LLMConfig | None = None):
        self.settings = settings or Settings.from_env()
        self.llm = llm or LLMConfig.from_env()
        self.policy = PolicyIndex(self.settings.policy_path)
        self.audit = AuditLog(self.settings.audit_path)

    # ---- samples -------------------------------------------------------------------
    def list_samples(self) -> list[dict]:
        index = self.settings.samples_dir / "cases.json"
        return json.loads(index.read_text(encoding="utf-8")) if index.exists() else []

    def sample_files(self, case_id: str) -> list[tuple[str, bytes]]:
        case = next((c for c in self.list_samples() if c["case_id"].lower() == case_id.lower()), None)
        if not case:
            raise KeyError(case_id)
        folder = self.settings.samples_dir / case["folder"]
        return [(p.name, p.read_bytes()) for p in sorted(folder.glob("*.pdf"))]

    def assess_sample(self, case_id: str) -> dict:
        return self.assess_files(self.sample_files(case_id), as_of=SAMPLE_AS_OF, case_id=case_id.upper())

    # ---- assessment ----------------------------------------------------------------
    def assess_files(self, files: list[tuple[str, bytes]], as_of: date | None = None,
                     case_id: str = "UPLOAD") -> dict:
        as_of = as_of or today()
        documents: list[Document] = []
        errors: list[str] = []
        for name, content in files:
            try:
                documents.append(load_document(name, content))
            except DocumentError as exc:
                errors.append(str(exc))
        extraction = extract(documents, self.llm, self.settings.send_documents_to_llm)
        extraction.warnings.extend(errors)
        facts, rules, verdict = evaluate(extraction, as_of)
        application = {k: extraction.value("loan_application", k)
                       for k in ("requested_amount", "term_months", "purpose")}
        clauses = {r.clause_id: self.policy.get(r.clause_id) for r in rules}
        narrative = llm_narrative(self.llm, application, facts, rules, verdict,
                                  [c.text for c in clauses.values() if c])
        rule_dicts = []
        for rule in rules:
            item = rule.to_dict()
            clause = clauses.get(rule.clause_id)
            item["clause_text"] = clause.text if clause else None
            rule_dicts.append(item)
        applicant = extraction.value("cccd", "full_name") or extraction.value("loan_application", "full_name")
        audit_id = self.audit.write("credit_assessment", {
            "case_id": case_id,
            "as_of": as_of.isoformat(),
            "applicant_id": mask_id(extraction.value("cccd", "id_number")),
            "documents": [{"file": d.filename, "type": d.doc_type, "sha256": d.sha256[:16]} for d in documents],
            "provider": self.llm.provider,
            "narrative_source": narrative["source"],
            "policy_version": self.policy.version,
            "rule_status": {r.rule_id: r.status for r in rules},
            "verdict": verdict,
        })
        return {
            "case_id": case_id,
            "applicant": applicant,
            "applicant_id_masked": mask_id(extraction.value("cccd", "id_number")),
            "as_of": as_of.isoformat(),
            "verdict": verdict,
            "verdict_label": VERDICTS[verdict],
            "facts": facts.to_dict(),
            "rules": rule_dicts,
            "narrative": narrative,
            "extraction": extraction.to_dict(),
            "policy_version": self.policy.version,
            "provider": self.llm.provider,
            "audit_id": audit_id,
            "disclaimer": "Kết quả chỉ mang tính đề xuất. Quyết định cuối cùng thuộc cấp phê duyệt (Điều 6.4).",
        }

    # ---- policy Q&A (RAG) ----------------------------------------------------------
    def ask_policy(self, question: str) -> dict:
        question = question.strip()[:500]
        hits = [(c, s) for c, s in self.policy.search(question, k=3) if s >= MIN_POLICY_SCORE]
        if hits and self.policy.coverage(question, hits[0][0]) < MIN_QUERY_COVERAGE:
            hits = []  # best clause shares too few words with the question: likely off-topic
        sources = [{**c.to_dict(), "score": s} for c, s in hits]
        if not hits:
            answer = {"answer": "Không tìm thấy quy định liên quan trong chính sách hiện hành. "
                                "Vui lòng hỏi lại hoặc liên hệ bộ phận quản lý chính sách.",
                      "cited": [], "source": "refusal"}
        else:
            answer = self._answer_from_clauses(question, [c for c, _ in hits])
        self.audit.write("policy_question", {"question": question, "cited": answer["cited"],
                                             "source": answer["source"], "provider": self.llm.provider})
        return {**answer, "sources": sources, "policy_version": self.policy.version}

    def _answer_from_clauses(self, question: str, clauses: list) -> dict:
        top = clauses[0]
        ref = top.clause_id if top.clause_id.startswith("Điều") else f"Điều {top.clause_id}"
        extractive = {"answer": f"Theo {ref} ({top.article}): {top.text}",
                      "cited": [top.clause_id], "source": "extractive"}
        if not self.llm.enabled:
            return extractive
        context = "\n".join(f"[{c.clause_id}] {c.text}" for c in clauses)
        system = ("Trả lời câu hỏi về chính sách cho vay CHỈ dựa trên các điều khoản được cung cấp. "
                  "Nếu điều khoản không đủ để trả lời, nói rõ là không có thông tin. "
                  "Trả về JSON {\"answer\": str, \"cited\": [mã điều khoản đã dùng]}.")
        try:
            result = complete_json(self.llm, system, f"Điều khoản:\n{context}\n\nCâu hỏi: {question}")
        except LLMError as exc:
            return {**extractive, "fallback_reason": str(exc)}
        valid_ids = {c.clause_id for c in clauses}
        cited = [str(x) for x in result.get("cited", []) if str(x) in valid_ids]
        text = str(result.get("answer", "")).strip()
        unknown = numbers_in(text) - numbers_in(context + " " + question)
        if not text or not cited or unknown:
            return {**extractive, "fallback_reason": "answer not grounded in retrieved clauses"}
        return {"answer": text, "cited": cited, "source": self.llm.provider}
