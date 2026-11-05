import re
import unicodedata


def normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


def suspicious(value: str) -> bool:
    # Supplemental detection only. Authority separation is the primary defense.
    cleaned = unicodedata.normalize("NFKC", value)
    cleaned = "".join(c for c in cleaned if unicodedata.category(c) != "Cf")
    return bool(
        re.search(
            r"ignore.{0,40}(instruction|rule)|system\s*(prompt|message)|"
            r"bypass|jailbreak|approve\s*(all|this)|mark.{0,20}approved|"
            r"bo qua.{0,20}(quy|luat)|bỏ qua.{0,20}(quy|luật)|"
            r"duyệt tất cả|tiết lộ.{0,20}(khóa|mật)|reveal.{0,20}(secret|key)",
            cleaned,
            re.I | re.S,
        )
    )


def safe_note(value: str) -> bool:
    return not suspicious(value) and not re.search(
        r"https?://|<|>|approved|đã duyệt|được duyệt|đủ điều kiện|"
        r"sẵn sàng.{0,10}duyệt|api.?key|password|token",
        value,
        re.I,
    )
