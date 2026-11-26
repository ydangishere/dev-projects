"""Load uploaded files into page text and classify the document type."""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass, field

from pypdf import PdfReader

from .textutil import norm

DOC_TYPES = {
    "cccd": "Căn cước công dân",
    "loan_application": "Giấy đề nghị vay vốn",
    "labor_contract": "Hợp đồng lao động",
    "bank_statement": "Sao kê tài khoản lương",
}

# Title keywords (accent-free) used to recognise each document.
_SIGNATURES = [
    ("loan_application", ("giay de nghi vay", "don de nghi vay", "de nghi cap tin dung")),
    ("labor_contract", ("hop dong lao dong",)),
    ("bank_statement", ("sao ke tai khoan", "bang ke giao dich")),
    ("cccd", ("can cuoc cong dan", "so dinh danh ca nhan")),
]


class DocumentError(ValueError):
    pass


@dataclass
class Document:
    filename: str
    pages: list[str]
    sha256: str
    doc_type: str = "unknown"
    notes: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return DOC_TYPES.get(self.doc_type, "Không xác định")

    def lines(self):
        """Yield (page_number, line_text) for every non-empty line."""
        for page_number, text in enumerate(self.pages, start=1):
            for line in text.splitlines():
                if line.strip():
                    yield page_number, line.strip()


def classify(pages: list[str]) -> str:
    head = norm(" ".join(pages)[:600])
    for doc_type, keywords in _SIGNATURES:
        if any(keyword in head for keyword in keywords):
            return doc_type
    return "unknown"


def load_document(filename: str, content: bytes, max_bytes: int = 10 * 1024 * 1024) -> Document:
    if len(content) > max_bytes:
        raise DocumentError(f"{filename}: file is larger than {max_bytes // 1024 // 1024} MB")
    lower = filename.lower()
    if lower.endswith(".pdf"):
        try:
            reader = PdfReader(io.BytesIO(content))
            pages = [page.extract_text() or "" for page in reader.pages]
        except Exception as exc:  # pypdf raises many exception types for bad files
            raise DocumentError(f"{filename}: cannot read PDF ({exc})") from exc
    elif lower.endswith((".txt", ".md")):
        pages = content.decode("utf-8", errors="replace").split("\f")
    else:
        raise DocumentError(f"{filename}: only PDF or TXT is supported in this demo")
    doc = Document(filename=filename, pages=pages, sha256=hashlib.sha256(content).hexdigest())
    if not "".join(pages).strip():
        doc.notes.append("Không đọc được chữ (có thể là ảnh scan; bản demo chưa có OCR)")
    doc.doc_type = classify(pages)
    return doc
