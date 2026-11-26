"""LLM intent parser, used only when the rule parser returns 'unknown'.

The model returns a small JSON object. Nothing it says is trusted blindly:
* the intent must be one of the known intents;
* an amount is accepted only if the exact text the model points to exists in the
  customer's message AND the rule parser reads the same amount from it;
* a beneficiary is accepted only if it resolves to a saved contact.
"""

from __future__ import annotations

import json

from .llm import LLMConfig, LLMError, complete_json
from .nlu import CATEGORY_KEYWORDS, INTENTS, Intent, match_beneficiaries, parse_amount, parse_period
from .textutil import norm

PERIODS = ["this_month", "last_month", "this_week", "last_7_days", "today", "yesterday"]

SYSTEM = (
    "Bạn phân loại tin nhắn của khách hàng ngân hàng thành JSON, không trả lời khách. "
    f"intent thuộc: {INTENTS + ['unknown']}. "
    "Trả về đúng các khóa: intent, amount_text (đoạn nguyên văn chỉ số tiền trong tin nhắn hoặc null), "
    "beneficiary (tên người nhận như khách viết hoặc null), "
    f"category (một trong {list(CATEGORY_KEYWORDS)} hoặc null), period (một trong {PERIODS} hoặc null), "
    "limit (số giao dịch hoặc null). Không suy đoán số tiền."
)


def parse_with_llm(config: LLMConfig, message: str, beneficiaries: list[dict]) -> Intent | None:
    if not config.enabled:
        return None
    contacts = [{"name": b["name"], "aliases": b["aliases"]} for b in beneficiaries]
    user = f"Danh bạ: {json.dumps(contacts, ensure_ascii=False)}\nTin nhắn: {message}"
    try:
        data = complete_json(config, SYSTEM, user)
    except LLMError:
        return None
    intent = data.get("intent")
    if intent not in INTENTS:
        return Intent("unknown", source="llm")

    slots: dict = {}
    if intent == "transfer":
        amount = None
        amount_text = data.get("amount_text")
        if isinstance(amount_text, str) and norm(amount_text) and norm(amount_text) in norm(message):
            parsed = parse_amount(amount_text)
            amount = parsed[0] if parsed else None
        name = data.get("beneficiary")
        ids = match_beneficiaries(str(name), beneficiaries) if name else []
        slots = {"amount": amount, "amount_text": amount_text if amount else None,
                 "beneficiary_ids": ids, "mentioned_name": norm(str(name)) if name and not ids else None}
    elif intent == "spending":
        category = data.get("category") if data.get("category") in CATEGORY_KEYWORDS else None
        period = data.get("period") if data.get("period") in PERIODS else None
        slots = {"category": category, **({"period": period} if period else parse_period(message))}
    elif intent == "transactions":
        limit = data.get("limit")
        slots = {"limit": min(int(limit), 20) if isinstance(limit, int) and limit > 0 else 5}
    return Intent(intent, slots, source="llm")
