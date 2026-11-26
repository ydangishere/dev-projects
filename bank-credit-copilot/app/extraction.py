"""Extract applicant facts from the documents, keeping the source of every value.

Regex extraction runs first and works offline on documents with the usual labels.
If an LLM is configured AND sending documents to it is allowed (LLM_SEND_DOCUMENTS),
the model only fills the fields regex missed. Before that:
* lines that try to instruct the AI are removed (guard.injection_lines);
* ID numbers, account numbers and names are replaced by placeholders (pii.Masker).
Each model answer must point to a line, and its value must literally appear in that
line after unmasking; otherwise the answer is dropped as a fabrication.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from .documents import Document
from .guard import injection_lines
from .llm import LLMConfig, LLMError, complete_json
from .observability import traced
from .pii import Masker
from .pii import engine_name as pii_engine_name
from .textutil import norm, parse_date, parse_vnd, strip_accents

INDEFINITE = "khong thoi han"


def _text(value: str) -> str | None:
    value = value.strip()
    return value or None


def _id(value: str) -> str | None:
    digits = re.sub(r"\D", "", value)
    return digits if 9 <= len(digits) <= 12 else None  # CMND has 9 digits, CCCD 12


def _date_or_indefinite(value: str) -> date | str | None:
    if INDEFINITE in norm(value):
        return INDEFINITE
    return parse_date(value)


def _int(value: str) -> int | None:
    match = re.search(r"\d+", value)
    return int(match.group(0)) if match else None


Parser = Callable[[str], Any]

# doc_type -> list of (field, accent-free label prefixes, parser, description for the LLM)
FIELD_SPECS: dict[str, list[tuple[str, tuple[str, ...], Parser, str]]] = {
    "cccd": [
        ("full_name", ("ho va ten",), _text, "họ và tên (giữ nguyên nếu là <PERSON_n>)"),
        ("id_number", ("so dinh danh ca nhan", "so cccd"), _id, "số CCCD 12 chữ số (giữ nguyên nếu là <CCCD_n>)"),
        ("date_of_birth", ("ngay sinh",), parse_date, "ngày sinh dd/mm/yyyy"),
        ("expiry_date", ("co gia tri den",), _date_or_indefinite, "ngày hết hạn hoặc 'Không thời hạn'"),
    ],
    "loan_application": [
        ("full_name", ("ho va ten khach hang", "ho va ten"), _text, "họ tên người đề nghị vay (giữ nguyên nếu là <PERSON_n>)"),
        ("id_number", ("so cccd",), _id, "số căn cước/CCCD (giữ nguyên nếu là <CCCD_n>)"),
        ("requested_amount", ("so tien de nghi vay", "so tien vay"), parse_vnd, "số tiền đề nghị vay (VND)"),
        ("term_months", ("thoi han vay",), _int, "thời hạn vay (tháng)"),
        ("purpose", ("muc dich vay",), _text, "mục đích vay"),
        ("existing_monthly_debt", ("nghia vu tra no hien tai",), parse_vnd,
         "nghĩa vụ trả nợ hiện tại mỗi tháng (VND)"),
    ],
    "labor_contract": [
        ("employer", ("ben su dung lao dong",), _text, "tên đơn vị sử dụng lao động"),
        ("full_name", ("nguoi lao dong",), _text, "họ tên người lao động"),
        ("id_number", ("so cccd",), _id, "số CCCD"),
        ("contract_type", ("loai hop dong",), _text, "loại hợp đồng: không xác định thời hạn, hoặc xác định thời hạn"),
        ("start_date", ("ngay bat dau",), parse_date, "ngày bắt đầu"),
        ("end_date", ("ngay ket thuc",), parse_date, "ngày kết thúc (nếu có)"),
        ("monthly_salary", ("muc luong",), parse_vnd, "mức lương tháng (VND)"),
    ],
    "bank_statement": [
        ("account_holder", ("chu tai khoan",), _text, "tên chủ tài khoản"),
        ("id_number", ("so giay to", "so cccd"), _id, "số giấy tờ tùy thân"),
        ("account_number", ("so tai khoan",), _text, "số tài khoản"),
    ],
}

_ROW = re.compile(r"(\d{1,2}/\d{1,2}/\d{4})\s*\|\s*(.+?)\s*\|\s*([+-])\s*([\d.,]+)")


@dataclass
class Evidence:
    value: Any
    raw: str
    filename: str
    page: int
    method: str = "regex"

    def to_dict(self) -> dict:
        value = self.value.isoformat() if isinstance(self.value, date) else self.value
        return {"value": value, "raw": self.raw, "filename": self.filename,
                "page": self.page, "method": self.method}


@dataclass
class SalaryCredit:
    date: date
    amount: int
    description: str
    filename: str
    page: int
    raw: str

    def to_dict(self) -> dict:
        return {"date": self.date.isoformat(), "amount": self.amount,
                "description": self.description, "filename": self.filename,
                "page": self.page, "raw": self.raw}


@dataclass
class Extraction:
    documents: list[Document]
    fields: dict[str, dict[str, Evidence]] = field(default_factory=dict)
    salary_credits: list[SalaryCredit] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    security_flags: list[dict] = field(default_factory=list)
    pii: dict = field(default_factory=dict)
    _skip: dict[str, set[int]] = field(default_factory=dict, repr=False)

    def get(self, doc_type: str, name: str) -> Evidence | None:
        return self.fields.get(doc_type, {}).get(name)

    def value(self, doc_type: str, name: str) -> Any:
        evidence = self.get(doc_type, name)
        return evidence.value if evidence else None

    def to_dict(self) -> dict:
        return {
            "documents": [{"filename": d.filename, "doc_type": d.doc_type, "label": d.label,
                           "pages": len(d.pages), "sha256": d.sha256, "notes": d.notes}
                          for d in self.documents],
            "fields": {dt: {k: ev.to_dict() for k, ev in fs.items()} for dt, fs in self.fields.items()},
            "salary_credits": [s.to_dict() for s in self.salary_credits],
            "warnings": self.warnings,
            "security_flags": self.security_flags,
            "pii": self.pii,
        }


def _value_after_label(line: str) -> str:
    return line.split(":", 1)[1] if ":" in line else ""


def extract_regex(doc: Document) -> tuple[dict[str, Evidence], list[SalaryCredit]]:
    found: dict[str, Evidence] = {}
    credits: list[SalaryCredit] = []
    specs = FIELD_SPECS.get(doc.doc_type, [])
    for page, line in doc.lines():
        key = norm(line)
        for name, labels, parser, _ in specs:
            if name in found:
                continue
            if any(key.startswith(label) for label in labels):
                value = parser(_value_after_label(line))
                if value is not None:
                    found[name] = Evidence(value, line, doc.filename, page)
                break
        if doc.doc_type == "labor_contract" and "contract_type" not in found:
            # contract type often sits inside a sentence: "Thời hạn hợp đồng: không xác định thời hạn, kể từ ..."
            term = re.search(r"(khong xac dinh thoi han|xac dinh thoi han(?: \d+ thang)?)", key)
            if term:
                label = "Không xác định thời hạn" if term.group(1).startswith("khong") else \
                    "Xác định thời hạn" + term.group(1)[len("xac dinh thoi han"):].replace("thang", "tháng")
                found["contract_type"] = Evidence(label, line, doc.filename, page)
        if doc.doc_type == "bank_statement":
            match = _ROW.search(line)
            if match and match.group(3) == "+" and "luong" in norm(match.group(2)):
                txn_date = parse_date(match.group(1))
                amount = parse_vnd(match.group(4))
                if txn_date and amount:
                    credits.append(SalaryCredit(txn_date, amount, match.group(2).strip(),
                                                doc.filename, page, line))
    return found, credits


def _grounded(value: Any, line: str) -> bool:
    """True when the value the model returned literally appears in the cited line."""
    if value == INDEFINITE:
        return INDEFINITE in norm(line)
    if isinstance(value, date):
        return any(form in line for form in (value.strftime("%d/%m/%Y"), f"{value.day}/{value.month}/{value.year}"))
    if isinstance(value, int):
        return re.search(rf"(?<!\d){value}(?!\d)", re.sub(r"(?<=\d)[.,\s](?=\d)", "", line)) is not None
    text = norm(str(value))
    return len(text) >= 2 and text in norm(line)


@traced("llm-extract-fields")
def _llm_fill(doc: Document, missing: list[tuple[str, Parser, str]], config: LLMConfig,
              masker: Masker, skip: set[int]) -> dict[str, Evidence]:
    """Ask the model for fields the regex missed.

    The model sees masked lines (no ID numbers or names) and must answer with a line id.
    An answer is kept only if, after unmasking, its value literally appears in that line;
    the value is then parsed by the same deterministic parser as the regex path.
    """
    lines = list(doc.lines())
    shown = [(i, page, line) for i, (page, line) in enumerate(lines) if i not in skip]
    body = "\n".join(f"[L{i}] {masker.mask(line)}" for i, _, line in shown)
    schema = {name: desc for name, _, desc in missing}
    system = ("Bạn trích xuất thông tin từ giấy tờ ngân hàng. Chỉ dùng nội dung có trong văn bản, không suy đoán. "
              "Các giá trị dạng <PERSON_1>, <CCCD_1> là thông tin đã được che: giữ nguyên chúng. "
              "Trả về JSON, mỗi khóa là tên trường, giá trị là {\"value\": chuỗi, \"line\": \"L<số dòng>\"} "
              "hoặc null nếu văn bản không có. Ngày ghi dạng dd/mm/yyyy, số tiền ghi bằng chữ số.")
    user = (f"Loại giấy tờ: {doc.label}\nCác trường cần lấy:\n{json.dumps(schema, ensure_ascii=False)}"
            f"\n\nVăn bản (mỗi dòng có mã [L..]):\n{body[:12000]}")
    try:
        answer = complete_json(config, system, user, purpose="extract", max_tokens=900)
    except LLMError:
        return {}
    by_id = {f"L{i}": (page, line) for i, page, line in shown}
    filled: dict[str, Evidence] = {}
    if isinstance(answer.get("fields"), dict):  # some models nest the answer
        answer = answer["fields"]
    for name, parser, _ in missing:
        item = answer.get(name)
        if isinstance(item, (str, int, float)):  # small models often drop the {"value", "line"} wrapper
            item = {"value": item}
        if not isinstance(item, dict) or item.get("value") in (None, "", "null"):
            continue
        raw = masker.unmask(str(item["value"]))
        value = parser(raw)
        if value is None:
            continue
        cited = by_id.get(str(item.get("line", "")).strip().upper().replace("[", "").replace("]", ""))
        candidates = [cited] if cited else []
        candidates += [(p, ln) for _, p, ln in shown if (p, ln) != cited]
        match = next(((p, ln) for p, ln in candidates if _grounded(value, ln)), None)
        if match:  # otherwise the value is not in the document: treat it as fabricated and drop it
            filled[name] = Evidence(value, match[1], doc.filename, match[0], method="llm")
    return filled


def _name_variants(names: list[str]) -> list[str]:
    variants: list[str] = []
    for name in names:
        variants += [name, name.upper(), strip_accents(name).upper()]
    return list(dict.fromkeys(v for v in variants if v))


@traced("extract")
def extract(documents: list[Document], config: LLMConfig | None = None,
            send_documents_to_llm: bool = False) -> Extraction:
    result = Extraction(documents=documents)
    accepted: list[Document] = []
    seen_types: set[str] = set()
    for doc in documents:
        if doc.doc_type == "unknown":
            result.warnings.append(f"{doc.filename}: không nhận diện được loại giấy tờ")
            continue
        if doc.doc_type in seen_types:
            result.warnings.append(f"{doc.filename}: trùng loại '{doc.label}', bản sau được bỏ qua")
            continue
        seen_types.add(doc.doc_type)
        accepted.append(doc)
        found, credits = extract_regex(doc)
        result.fields[doc.doc_type] = found
        result.salary_credits.extend(credits)
        flagged = injection_lines([line for _, line in doc.lines()])
        if flagged:
            all_lines = list(doc.lines())
            for index in flagged:
                page, line = all_lines[index]
                result.security_flags.append({"filename": doc.filename, "page": page, "line": line,
                                              "type": "prompt_injection"})
            result.warnings.append(f"{doc.filename}: có {len(flagged)} dòng chứa câu lệnh nhắm vào AI; "
                                   "các dòng này không được gửi cho mô hình")
        result._skip[doc.filename] = set(flagged)

    if config and config.enabled and send_documents_to_llm:
        names = [ev.value for fs in result.fields.values() for key, ev in fs.items()
                 if key in {"full_name", "account_holder"} and isinstance(ev.value, str)]
        masker = Masker(known_names=_name_variants(names))
        for doc in accepted:
            found = result.fields[doc.doc_type]
            missing = [(n, p, d) for n, _, p, d in FIELD_SPECS[doc.doc_type] if n not in found]
            if missing:
                found.update(_llm_fill(doc, missing, config, masker, result._skip.get(doc.filename, set())))
        result.pii = {"engine": pii_engine_name(), "masked": masker.counts}
    result.salary_credits.sort(key=lambda s: s.date)
    return result
