"""Checks that run BEFORE any intent parsing or LLM call.

Blocked messages never reach the model, so a prompt-injection attempt cannot change
what the assistant does. Every block is written to the audit log as a security event.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .textutil import has_word, norm

_RULES: list[tuple[str, list[str], str]] = [
    ("bypass_otp", [
        "bo qua otp", "khong can otp", "khong can ma otp", "khong can xac nhan", "bo qua xac nhan",
        "tu dong xac nhan", "chuyen luon khong can", "bo buoc otp", "tat otp", "skip otp", "without otp",
    ], "Mọi lệnh chuyển tiền đều phải được chính bạn xác nhận bằng mã OTP. Trợ lý không thể bỏ qua bước này."),
    ("prompt_injection", [
        "ignore previous instructions", "ignore all instructions", "ignore your instructions",
        "bo qua huong dan", "bo qua moi huong dan", "quen het huong dan", "system prompt", "developer mode",
        "che do nha phat trien", "jailbreak", "ban gio la", "dong vai admin", "ban la admin", "toi la admin",
        "toi la nhan vien ngan hang", "quyen quan tri",
    ], "Mình không thể thay đổi cách hoạt động hay quyền hạn của trợ lý. Mình chỉ hỗ trợ tài khoản của bạn."),
    ("other_customer_data", [
        "tai khoan cua nguoi khac", "so du cua nguoi khac", "thong tin khach hang khac",
        "tai khoan cua ong", "tai khoan cua ba", "so du cua ong", "so du cua ba", "so du cua anh", "so du cua chi",
        "giao dich cua nguoi khac", "danh sach khach hang",
    ], "Vì bảo mật, mình chỉ có thể tra cứu tài khoản của chính bạn."),
    ("new_beneficiary_or_account", [
        "doi so tai khoan", "sua so tai khoan", "them nguoi nhan", "so tai khoan moi", "chuyen vao so tai khoan",
        "chuyen den so tai khoan",
    ], "Vì an toàn, trợ lý chỉ chuyển tiền cho người đã có trong danh bạ. Thêm hoặc sửa người nhận "
       "cần thực hiện trong mục Danh bạ của ứng dụng, có xác thực riêng."),
]

_OUT_OF_SCOPE = [
    ("investment_advice", ["co nen dau tu", "mua co phieu", "co phieu nao", "bitcoin", "crypto", "coin nao",
                           "tien ao", "chung khoan nao", "nen mua vang"]),
]

OTP_IN_CHAT = re.compile(r"^\s*(?:otp|ma)?\s*:?\s*\d{6}\s*$")
_ACCOUNT_NUMBER = re.compile(r"(?<!\d)(\d[\d ]{8,}\d)(?!\d)")


@dataclass
class GuardrailResult:
    allowed: bool
    category: str | None = None
    message: str | None = None
    security_event: bool = False


def check(message: str) -> GuardrailResult:
    t = norm(message)
    if not t:
        return GuardrailResult(False, "empty", "Bạn cần mình hỗ trợ gì?")
    if len(message) > 500:
        return GuardrailResult(False, "too_long", "Tin nhắn quá dài, bạn vui lòng viết ngắn gọn hơn (tối đa 500 ký tự).")
    if OTP_IN_CHAT.match(t):
        return GuardrailResult(False, "otp_in_chat",
                               "Đừng gửi mã OTP vào khung chat. Hãy nhập OTP vào ô xác nhận của lệnh chuyển. "
                               "Ngân hàng và trợ lý không bao giờ hỏi mã OTP qua tin nhắn.", security_event=True)
    for category, phrases, reply in _RULES:
        if any(has_word(t, p) for p in phrases):
            return GuardrailResult(False, category, reply, security_event=True)
    if _ACCOUNT_NUMBER.search(message) and has_word(t, "chuyen"):
        return GuardrailResult(False, "new_beneficiary_or_account", _RULES[3][2], security_event=True)
    for category, phrases in _OUT_OF_SCOPE:
        if any(has_word(t, p) for p in phrases):
            return GuardrailResult(False, category,
                                   "Mình không đưa ra khuyến nghị đầu tư. Bạn có thể liên hệ chuyên viên tư vấn "
                                   "của ngân hàng. Mình có thể giúp xem số dư, chi tiêu hoặc chuyển tiền.")
    return GuardrailResult(True)


def mask_for_log(text: str) -> str:
    """Hide anything that looks like an account/card number or an OTP before logging."""
    if OTP_IN_CHAT.match(norm(text)):
        return "******"
    return _ACCOUNT_NUMBER.sub(lambda m: "****" + re.sub(r"\D", "", m.group(1))[-4:], text)
