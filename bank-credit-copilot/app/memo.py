"""Write the credit memo narrative.

Offline mode uses a template. With an LLM, the model rewrites the summary from masked,
already-computed facts; every number in its text must appear in those facts or in the
cited clauses, otherwise the template is used instead (anti-fabrication check).
"""

from __future__ import annotations

import json
import re

from .llm import LLMConfig, LLMError, complete_json
from .rules import FAIL, NEED_INFO, PASS, VERDICTS, Facts, RuleResult
from .textutil import fmt_vnd

_NUMBER = re.compile(r"\d[\d.,]*")


def numbers_in(text: str) -> set[str]:
    """Normalise numbers so '8.197.358', '8,197,358' and '8197358' compare equal."""
    return {re.sub(r"[.,]", "", n).lstrip("0") or "0" for n in _NUMBER.findall(text)}


def template_narrative(application: dict, facts: Facts, rules: list[RuleResult], verdict: str) -> dict:
    passed = sum(r.status == PASS for r in rules)
    parts = []
    if application.get("requested_amount"):
        parts.append(f"Khách hàng đề nghị vay {fmt_vnd(application['requested_amount'])} trong "
                     f"{application.get('term_months', '—')} tháng, mục đích: {application.get('purpose') or '—'}.")
    if facts.income:
        dti = f"{facts.dti * 100:.1f}%" if facts.dti is not None else "chưa tính được"
        parts.append(f"Thu nhập dùng để xét duyệt {fmt_vnd(facts.income)}/tháng; DTI {dti}.")
    parts.append(f"Đạt {passed}/{len(rules)} điều kiện kiểm tra tự động.")
    risks = [f"{r.title} (Điều {r.clause_id}): {r.detail}" for r in rules if r.status == FAIL]
    questions = [f"{r.title}: {r.detail}" for r in rules if r.status == NEED_INFO]
    parts.append(f"Đề xuất: {VERDICTS[verdict]}.")
    return {"summary": " ".join(parts), "risks": risks, "follow_ups": questions, "source": "template"}


def llm_narrative(config: LLMConfig, application: dict, facts: Facts, rules: list[RuleResult],
                  verdict: str, clause_texts: list[str]) -> dict:
    fallback = template_narrative(application, facts, rules, verdict)
    if not config.enabled:
        return fallback
    masked = {  # no name, ID or account number leaves the bank (policy Điều 7)
        "khoan_vay": {k: application.get(k) for k in ("requested_amount", "term_months", "purpose")},
        "so_lieu": facts.to_dict(),
        "dieu_kien": [{"ten": r.title, "dieu": r.clause_id, "ket_qua": r.status, "chi_tiet": r.detail}
                      for r in rules],
        "de_xuat": VERDICTS[verdict],
    }
    system = ("Bạn là chuyên viên thẩm định tín dụng. Viết tờ trình ngắn gọn bằng tiếng Việt từ dữ liệu "
              "đã được tính sẵn. Không thay đổi kết quả, không thêm con số mới, không đưa ra quyết định "
              "cuối cùng. Trả về JSON: {\"summary\": str, \"risks\": [str], \"follow_ups\": [str]}.")
    try:
        answer = complete_json(config, system, json.dumps(masked, ensure_ascii=False))
    except LLMError as exc:
        return {**fallback, "fallback_reason": str(exc)}
    summary = str(answer.get("summary", "")).strip()
    risks = [str(x) for x in answer.get("risks", []) if str(x).strip()]
    follow_ups = [str(x) for x in answer.get("follow_ups", []) if str(x).strip()]
    allowed = numbers_in(json.dumps(masked, ensure_ascii=False) + " ".join(clause_texts))
    allowed |= numbers_in(" ".join(fmt_vnd(v) for v in facts.to_dict().values() if isinstance(v, (int, float))))
    produced = numbers_in(" ".join([summary, *risks, *follow_ups]))
    unknown = sorted(produced - allowed)
    if not summary or unknown:
        reason = "empty summary" if not summary else f"numbers not found in facts: {', '.join(unknown[:5])}"
        return {**fallback, "fallback_reason": reason}
    return {"summary": summary, "risks": risks, "follow_ups": follow_ups, "source": config.provider}
