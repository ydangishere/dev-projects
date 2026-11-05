from datetime import date

from .models import Finding, parse_date
from .security import normalize, suspicious


def evaluate(application, documents, extracted, rules, today: date, mode: str):
    findings = []

    def add(rule, code, message, doc=None, fact=None, severity="review"):
        findings.append(
            Finding(
                id=f"F{len(findings) + 1}",
                rule=rule,
                code=code,
                severity=severity,
                message=message,
                document_id=doc["id"] if doc else None,
                page=fact.page if fact else None,
                field=fact.field if fact else None,
                quote=fact.quote if fact else None,
                source="document" if fact else "manifest",
            )
        )

    by_kind = {d["kind"]: d for d in documents}
    for kind in rules["required_documents"]:
        if kind not in by_kind:
            add("R1", "missing_document", f"Thiếu giấy tờ: {kind}.", severity="blocker")
    for doc in documents:
        if (
            doc["verification"] != "verified"
            or doc["verified_version"] != doc["version"]
        ):
            add(
                "R4",
                "unverified_version",
                "Phiên bản giấy tờ hiện tại chưa được xác minh.",
                doc,
            )
        result = extracted.get(doc["id"])
        if result is None:
            add(
                "R5",
                "extraction_failed",
                "Không đọc được giấy tờ; nhân viên cần kiểm tra bản gốc.",
                doc,
            )
            continue
        if mode == "gemini":
            add(
                "R7",
                "ocr_needs_review",
                "Thông tin do AI đọc cần nhân viên đối chiếu bản gốc.",
                doc,
            )
        facts = {}
        for fact in result.facts:
            if fact.field in facts:
                add(
                    "R5",
                    "duplicate_fact",
                    "Có nhiều giá trị cho cùng một trường; cần kiểm tra.",
                    doc,
                    fact,
                )
                facts[fact.field] = None
                continue
            facts[fact.field] = fact
            if suspicious(fact.value + " " + fact.quote):
                add(
                    "R6",
                    "suspicious_content",
                    "Phát hiện nội dung giống chỉ dẫn thao túng; cần kiểm tra.",
                    doc,
                    fact,
                )
                facts[fact.field] = None
            elif fact.confidence < rules["minimum_confidence"]:
                add(
                    "R5",
                    "low_confidence",
                    "Thông tin đọc chưa đủ chắc chắn.",
                    doc,
                    fact,
                )
                facts[fact.field] = None
            elif normalize(fact.value) not in normalize(fact.quote):
                add(
                    "R5",
                    "ungrounded_value",
                    "Giá trị không khớp trích đoạn; cần kiểm tra.",
                    doc,
                    fact,
                )
                facts[fact.field] = None
        required = []
        if doc["kind"] == "business_license":
            required += ["legal_name", "registration_number"]
        if doc["kind"] == "bank_confirmation":
            required += ["legal_name"]
        if doc["kind"] in rules["expiry_required"]:
            required += ["expires_on"]
        for field in required:
            if not facts.get(field):
                add(
                    "R5", "missing_fact", f"Chưa xác định được thông tin: {field}.", doc
                )
        expiry = facts.get("expires_on")
        if expiry:
            try:
                if parse_date(expiry.value) < today:
                    add(
                        "R2",
                        "expired",
                        "Giấy tờ đã hết hạn tại ngày kiểm tra.",
                        doc,
                        expiry,
                        "blocker",
                    )
            except ValueError:
                add(
                    "R5",
                    "invalid_date",
                    "Ngày hết hạn không rõ hoặc không hợp lệ.",
                    doc,
                    expiry,
                )
        for field in ["legal_name", "registration_number"]:
            fact = facts.get(field)
            relevant = doc["kind"] == "business_license" or (
                doc["kind"] == "bank_confirmation" and field == "legal_name"
            )
            if (
                fact
                and relevant
                and normalize(fact.value) != normalize(application[field])
            ):
                add(
                    "R3",
                    "mismatch",
                    f"Thông tin {field} không khớp với hồ sơ MMS; cần đối chiếu.",
                    doc,
                    fact,
                )
    return findings
