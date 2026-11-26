"""Extract applicant facts from the documents, keeping the source of every value.

Regex extraction runs first and works offline on the labelled sample documents.
If an LLM is configured AND sending documents to it is allowed, the model only fills
fields that regex missed, and each model answer must quote a line that really exists
in the document. Values are always re-parsed from that quote by deterministic code.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from .documents import Document
from .llm import LLMConfig, LLMError, complete_json
from .textutil import norm, parse_date, parse_vnd

INDEFINITE = "khong thoi han"


def _text(value: str) -> str | None:
    value = value.strip()
    return value or None


def _id(value: str) -> str | None:
    digits = re.sub(r"\D", "", value)
    return digits or None


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
        ("full_name", ("ho va ten",), _text, "họ và tên"),
        ("id_number", ("so dinh danh ca nhan", "so cccd"), _id, "số CCCD 12 chữ số"),
        ("date_of_birth", ("ngay sinh",), parse_date, "ngày sinh dd/mm/yyyy"),
        ("expiry_date", ("co gia tri den",), _date_or_indefinite, "ngày hết hạn hoặc 'Không thời hạn'"),
    ],
    "loan_application": [
        ("full_name", ("ho va ten khach hang", "ho va ten"), _text, "họ tên khách hàng"),
        ("id_number", ("so cccd",), _id, "số CCCD"),
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
        ("contract_type", ("loai hop dong",), _text, "loại hợp đồng"),
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
        if doc.doc_type == "bank_statement":
            match = _ROW.search(line)
            if match and match.group(3) == "+" and "luong" in norm(match.group(2)):
                txn_date = parse_date(match.group(1))
                amount = parse_vnd(match.group(4))
                if txn_date and amount:
                    credits.append(SalaryCredit(txn_date, amount, match.group(2).strip(),
                                                doc.filename, page, line))
    return found, credits


def _llm_fill(doc: Document, missing: list[tuple[str, Parser, str]], config: LLMConfig) -> dict[str, Evidence]:
    """Ask the model for missing fields; keep only answers backed by a verbatim quote."""
    schema = {name: f"{desc}. Trả về {{\"value\": ..., \"quote\": dòng nguyên văn}} hoặc null"
              for name, _, desc in missing}
    system = ("Bạn trích xuất thông tin từ giấy tờ ngân hàng. Chỉ dùng nội dung có trong văn bản. "
              "Với mỗi trường, 'quote' phải là một dòng được sao chép nguyên văn từ văn bản. "
              "Không suy đoán. Trường không có thì trả về null. Chỉ trả về JSON.")
    body = "\n".join(f"[trang {p}] {line}" for p, line in doc.lines())
    user = f"Các trường cần trích xuất:\n{json.dumps(schema, ensure_ascii=False)}\n\nVăn bản:\n{body[:12000]}"
    try:
        answer = complete_json(config, system, user)
    except LLMError:
        return {}
    filled: dict[str, Evidence] = {}
    lines = list(doc.lines())
    for name, parser, _ in missing:
        item = answer.get(name)
        if not isinstance(item, dict) or not item.get("quote"):
            continue
        quote = norm(str(item["quote"]))
        match = next(((p, ln) for p, ln in lines if quote and quote in norm(ln)), None)
        if not match:
            continue  # quote not found in the document: treat as a fabrication and drop it
        page, line = match
        value = parser(_value_after_label(line) or line)
        if value is not None:
            filled[name] = Evidence(value, line, doc.filename, page, method="llm")
    return filled


def extract(documents: list[Document], config: LLMConfig | None = None,
            send_documents_to_llm: bool = False) -> Extraction:
    result = Extraction(documents=documents)
    seen_types: set[str] = set()
    for doc in documents:
        if doc.doc_type == "unknown":
            result.warnings.append(f"{doc.filename}: không nhận diện được loại giấy tờ")
            continue
        if doc.doc_type in seen_types:
            result.warnings.append(f"{doc.filename}: trùng loại '{doc.label}', bản sau được bỏ qua")
            continue
        seen_types.add(doc.doc_type)
        found, credits = extract_regex(doc)
        if config and config.enabled and send_documents_to_llm:
            missing = [(n, p, d) for n, _, p, d in FIELD_SPECS[doc.doc_type] if n not in found]
            if missing:
                found.update(_llm_fill(doc, missing, config))
        result.fields[doc.doc_type] = found
        result.salary_credits.extend(credits)
    result.salary_credits.sort(key=lambda s: s.date)
    return result
