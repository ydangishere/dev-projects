"""Linh is a simulated AI persona (not a real employee, human, or autonomous sender)."""
from __future__ import annotations

import json
import os
from urllib import error, request


def fallback_guide(payload: dict) -> str:
    vi = payload.get("language", "vi") == "vi"
    flow = payload["flow"]
    if flow == "skip":
        return "Linh: Bạn có thể bỏ qua và mời bạn bè sau." if vi else "Linh: You can skip and invite people later."
    if flow == "sync":
        if payload["permission"] in ("denied", "not_requested"):
            return ("Linh: Để hiện danh bạ trong app, bạn cần cấp quyền đọc danh bạ. Bạn vẫn có thể bỏ qua hoặc chọn người qua Contact Picker." if vi else
                    "Linh: In-app contact list requires OS permission. You may skip or use the native picker instead.")
        return ("Linh: App chỉ đồng bộ những contact bạn cho phép, và cần bạn đồng ý riêng trước khi gửi lên máy chủ." if vi else
                "Linh: Only permission-scoped contacts can be synced, with separate upload consent.")
    return ("Linh: Hãy chọn người qua Contact Picker (màn hình danh bạ) của điện thoại. Không cần cho app đọc toàn bộ danh bạ; bạn xác nhận trước khi chia sẻ lời mời." if vi else
            "Linh: Select contacts in the native picker. No full address-book permission is required; you confirm before sharing.")


def guide_onboarding(payload: dict) -> dict:
    """Optional OpenAI text generation with non-PII metadata; safe offline fallback."""
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    key = os.getenv("OPENAI_API_KEY", "")
    if not key:
        return {"persona": "Linh (simulated AI)", "mode": "rules_demo", "model": "none", "advice": fallback_guide(payload)}
    instruction = (
        "You are Linh, a clearly disclosed simulated AI onboarding assistant for a referral app. "
        "Respond in requested language, 65 words max. Two independent flows: "
        "Sync Contacts: app-managed list needs OS permission plus separate sync upload consent. "
        "Select to Invite: native system picker does not require full address-book permission. "
        "Always allow skip; you cannot read contacts, grant permission, upload data or send invites. "
        "Never claim to be a real employee or to have performed a real action."
    )
    try:
        body = json.dumps({"model": model, "temperature": 0.2,
                           "messages": [{"role": "system", "content": instruction},
                                        {"role": "user", "content": json.dumps(payload)}]})
        req = request.Request("https://api.openai.com/v1/chat/completions", data=body.encode(),
                              headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, method="POST")
        with request.urlopen(req, timeout=8) as response:
            data = json.load(response)
        answer = data["choices"][0]["message"]["content"]
        return {"persona": "Linh (simulated AI)", "mode": "optional_llm", "model": model, "advice": answer}
    except (error.URLError, TimeoutError, ValueError, KeyError, IndexError):
        return {"persona": "Linh (simulated AI)", "mode": "rules_fallback", "model": "none", "advice": fallback_guide(payload)}
