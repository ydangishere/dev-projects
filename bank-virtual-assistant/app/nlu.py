"""Rule-based Vietnamese intent parser (works offline, with or without accents).

It understands the phrasing customers actually type: "chuyển 500k cho mẹ",
"chuyen 1tr5 cho lan", "tháng này tiêu bao nhiêu cho ăn uống", "số dư còn bao nhiêu".
When it cannot classify a message the agent may ask an LLM (see llm_nlu.py).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .textutil import has_word, norm

INTENTS = ["greeting", "help", "balance", "spending", "transactions", "beneficiaries", "transfer", "cancel"]

CATEGORY_KEYWORDS = {
    "an_uong": ["an uong", "do an", "an trua", "an toi", "an sang", "an vat", "cafe", "ca phe", "nha hang",
                "grabfood", "shopeefood", "an"],
    "mua_sam": ["mua sam", "shopping", "shopee", "tiki", "mua do", "sieu thi"],
    "di_chuyen": ["di chuyen", "di lai", "grab", "taxi", "xang", "gui xe"],
    "hoa_don": ["hoa don", "tien dien", "tien nuoc", "dien nuoc", "internet", "wifi"],
    "giai_tri": ["giai tri", "xem phim", "phim", "spotify", "netflix"],
}

_SPENDING = ["chi tieu", "tieu", "da chi", "chi bao nhieu", "chi het", "tong chi", "xai", "ton bao nhieu", "chi phi",
             "het bao nhieu", "mat bao nhieu"]
_TRANSFER = ["chuyen", "ck", "gui tien", "chuyen tien", "chuyen khoan", "bank cho", "tra tien cho"]
_BALANCE = ["so du", "con bao nhieu", "tai khoan con", "balance", "kiem tra tai khoan", "trong tai khoan co"]
_TRANSACTIONS = ["giao dich", "lich su", "sao ke", "bien dong"]
_BENEFICIARIES = ["danh ba", "nguoi nhan", "nguoi thu huong", "danh sach nguoi"]
_HELP = ["giup gi", "lam duoc gi", "huong dan", "help", "tro giup", "ban la ai"]
_GREETING = ["xin chao", "chao", "hello", "hi", "alo", "chao ban"]
_CANCEL = ["huy", "khong chuyen nua", "thoi khong chuyen", "cancel", "dung lai"]
_NAME_STOP = {"nhe", "nha", "voi", "di", "giup", "ngay", "luon", "a", "ah", "em", "toi", "minh"}


@dataclass
class Intent:
    name: str
    slots: dict = field(default_factory=dict)
    source: str = "rules"

    def to_dict(self) -> dict:
        return {"name": self.name, "slots": self.slots, "source": self.source}


def _any(text: str, phrases: list[str]) -> bool:
    return any(has_word(text, p) for p in phrases)


def _number(raw: str) -> float:
    if re.fullmatch(r"\d+[.,]\d{1,2}", raw):
        return float(raw.replace(",", "."))
    return float(re.sub(r"[.,]", "", raw))


_AMOUNT_PATTERNS = [
    (re.compile(r"(\d+)\s*tram\s*(?:k|nghin|ngan)(?![a-z0-9])"), "hundred_k"),
    (re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:tr|trieu|cu)\s*(\d{1,3})?(?![a-z0-9])"), "million"),
    (re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:k|nghin|ngan|ng)(?![a-z0-9])"), "thousand"),
    (re.compile(r"(?<![\d.,])(\d{1,3}(?:[.,]\d{3})+)\s*(?:d|vnd|dong)?(?![a-z0-9])"), "grouped"),
    (re.compile(r"(?<![\d.,])(\d{4,9})\s*(?:d|vnd|dong)?(?![a-z0-9.,])"), "plain"),
]


def parse_amount(text: str) -> tuple[int, str] | None:
    """Return (amount in VND, matched text) for the first amount in `text`, else None."""
    t = norm(text)
    best: tuple[int, int, str] | None = None
    for pattern, kind in _AMOUNT_PATTERNS:
        for match in pattern.finditer(t):
            if kind == "hundred_k":
                value = int(match.group(1)) * 100_000
            elif kind == "million":
                value = _number(match.group(1)) * 1_000_000
                if match.group(2):
                    tail = match.group(2)
                    value += int(tail) * 10 ** (6 - len(tail))
            elif kind == "thousand":
                value = _number(match.group(1)) * 1_000
            else:
                value = _number(match.group(1))
            if value <= 0:
                continue
            if best is None or match.start() < best[0]:
                best = (match.start(), int(round(value)), match.group(0).strip())
            break
    return (best[1], best[2]) if best else None


def match_beneficiaries(text: str, beneficiaries: list[dict]) -> list[str]:
    """IDs of saved beneficiaries mentioned in `text` (by alias or full name)."""
    t = norm(text)
    found = []
    for b in beneficiaries:
        names = [norm(a) for a in b.get("aliases", [])] + [norm(b["name"])]
        if any(has_word(t, n) for n in names if n):
            found.append(b["beneficiary_id"])
    return found


def mentioned_name(text: str) -> str | None:
    """The words after 'cho' in a transfer request, e.g. 'cho chi Hoa nhe' -> 'chi hoa'."""
    match = re.search(r"(?<![a-z])cho\s+([a-z]+(?:\s+[a-z]+){0,2})", norm(text))
    if not match:
        return None
    words = [w for w in match.group(1).split() if w not in _NAME_STOP and not w.isdigit()]
    return " ".join(words) or None


def parse_category(text: str) -> str | None:
    t = norm(text)
    for category, words in CATEGORY_KEYWORDS.items():
        if _any(t, words):
            return category
    return None


def parse_period(text: str) -> dict:
    t = norm(text)
    month = re.search(r"thang (\d{1,2})(?:/(\d{4}))?(?![\d])", t)
    if has_word(t, "thang truoc"):
        return {"period": "last_month"}
    if month and 1 <= int(month.group(1)) <= 12:
        return {"period": "month", "month": int(month.group(1)),
                "year": int(month.group(2)) if month.group(2) else None}
    if has_word(t, "tuan nay"):
        return {"period": "this_week"}
    if _any(t, ["tuan truoc", "tuan qua", "7 ngay"]):
        return {"period": "last_7_days"}
    if has_word(t, "hom nay"):
        return {"period": "today"}
    if has_word(t, "hom qua"):
        return {"period": "yesterday"}
    return {"period": "this_month"}


def parse(text: str, beneficiaries: list[dict]) -> Intent:
    t = norm(text)
    without_travel = t.replace("di chuyen", " ")
    amount = parse_amount(text)
    people = match_beneficiaries(text, beneficiaries)

    if _any(t, _CANCEL):
        return Intent("cancel")
    sends_money = _any(without_travel, ["chuyen", "ck", "gui tien"])
    category = parse_category(text)
    period_words = _any(t, ["thang", "tuan", "hom nay", "hom qua"])
    asks_spending = _any(t, _SPENDING) or (category and (has_word(t, "chi") or has_word(t, "bao nhieu") or period_words))
    if asks_spending and not sends_money:
        return Intent("spending", {"category": category, **parse_period(text)})
    if _any(without_travel, _TRANSFER):
        return Intent("transfer", {"amount": amount[0] if amount else None,
                                   "amount_text": amount[1] if amount else None,
                                   "beneficiary_ids": people, "mentioned_name": mentioned_name(text)})
    if _any(t, _TRANSACTIONS):  # checked before balance: "biến động số dư" means transaction history
        count = re.search(r"(\d{1,2})\s*giao dich", t)
        return Intent("transactions", {"limit": min(int(count.group(1)), 20) if count else 5})
    if _any(t, _BALANCE):
        return Intent("balance")
    if _any(t, _BENEFICIARIES):
        return Intent("beneficiaries")
    if _any(t, _HELP):
        return Intent("help")
    if _any(t, _GREETING) and len(t.split()) <= 5:
        return Intent("greeting")
    if amount or people:  # a fragment such as "500k" or "cho Lan" while a transfer is pending
        return Intent("fragment", {"amount": amount[0] if amount else None,
                                   "amount_text": amount[1] if amount else None, "beneficiary_ids": people,
                                   "mentioned_name": mentioned_name(text)})
    return Intent("unknown")
