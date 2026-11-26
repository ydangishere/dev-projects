"""Vietnamese text helpers."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta, timezone

VN_TZ = timezone(timedelta(hours=7), "Asia/Ho_Chi_Minh")


def strip_accents(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    return "".join(ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn")


def norm(text: str) -> str:
    """Lowercase, accent-free, single-spaced. 'Chuyển 500K' -> 'chuyen 500k'."""
    return re.sub(r"\s+", " ", strip_accents(text).lower()).strip()


def has_word(text: str, phrase: str) -> bool:
    """Whole-word match on normalised text."""
    return re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", text) is not None


def fmt_vnd(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{round(value):,}".replace(",", ".") + " ₫"


def mask_account(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    return "****" + digits[-4:] if len(digits) >= 4 else "****"


def now_vn() -> datetime:
    return datetime.now(VN_TZ)
