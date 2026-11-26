"""Small Vietnamese text helpers shared by extraction, retrieval and rules."""

from __future__ import annotations

import calendar
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone


def strip_accents(text: str) -> str:
    """'Nguyễn Văn An' -> 'Nguyen Van An' (also maps đ/Đ)."""
    text = text.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def norm(text: str) -> str:
    """Lowercase, accent-free, single-spaced form used for matching."""
    return re.sub(r"\s+", " ", strip_accents(text).lower()).strip()


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", norm(text))


def parse_vnd(text: str) -> int | None:
    """Parse '25.000.000 VND', '25,000,000', '+24.800.000' into an int."""
    match = re.search(r"\d{1,3}(?:[.,]\d{3})+|\d+", text)
    if not match:
        return None
    return int(re.sub(r"[.,]", "", match.group(0)))


def parse_date(text: str) -> date | None:
    """dd/mm/yyyy (Vietnamese documents) or yyyy-mm-dd (what models often return)."""
    match = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", text)
    iso = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if match:
        day, month, year = (int(g) for g in match.groups())
    elif iso:
        year, month, day = (int(g) for g in iso.groups())
    else:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def fmt_vnd(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{round(value):,}".replace(",", ".") + " VND"


def fmt_date(value: date | None) -> str:
    return value.strftime("%d/%m/%Y") if value else "—"


def years_between(start: date, end: date) -> int:
    years = end.year - start.year
    if (end.month, end.day) < (start.month, start.day):
        years -= 1
    return years


def months_between(start: date, end: date) -> int:
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return months


def add_months(start: date, months: int) -> date:
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def mask_id(value: str | None) -> str:
    """Keep only the last 3 digits of an ID or account number (policy Điều 7.1)."""
    if not value:
        return "—"
    digits = re.sub(r"\s", "", value)
    return "*" * max(len(digits) - 3, 0) + digits[-3:]


VN_TZ = timezone(timedelta(hours=7), "Asia/Ho_Chi_Minh")


def today() -> date:
    return datetime.now(VN_TZ).date()
