"""Markdown/JSON report using the requested column order (Tình huống first)."""
import json
from datetime import datetime, timezone
from pathlib import Path
from .knowledge import SCENARIOS


def sanitize_md(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def report(results: list[dict], output: Path, mode: str) -> tuple[Path, Path]:
    output.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = ["# Bug Triage Report – Jira / Gmail", "", f"Generated: {now}",
             f"Data source: **{mode.upper()}**", "", 
             "> Đây là gợi ý phân loại lỗi, KHÔNG xác nhận bug đã tồn tại hoặc đã được sửa. Người phụ trách phải xác minh.",
             "", "## Danh sách lỗi được phân loại", "",
             "| ✓ | Tình huống | Vấn đề | Cách sửa | Dùng gì để sửa | Nguồn | Ưu tiên |",
             "|---|---|---|---|---|---|---|"]
    for x in results:
        source = x["source"].upper()+" "+x["source_id"]
        if x["source_url"]:
            source = f"[{sanitize_md(source)}]({x['source_url']})"
        fields = ["☐",x["situation"],x["problem"],x["fix"],x["tools"],source,x["priority"]]
        lines.append("| "+" | ".join(sanitize_md(v) if i!=5 else v for i,v in enumerate(fields))+" |")
    lines.extend(["", "## Checklist 15 tình huống tiêu chuẩn", "",
                  "| ✓ | Tình huống | Vấn đề | Cách sửa | Dùng gì để sửa |",
                  "|---|---|---|---|---|"])
    for s in SCENARIOS:
        lines.append("| "+" | ".join(["☐",*[sanitize_md(v) for v in (s.situation,s.problem,s.fix,s.tools)]])+" |")
    lines.extend(["", "## Nguyên tắc", "", "- Chế độ MOCK không đọc Jira hay Gmail thật.",
        "- AI chỉ **đề xuất**, không tự sửa code, ticket, gửi email hoặc đưa quyết định y tế.",
        "- Kiểm tra bằng log, code, dữ liệu hệ thống trước khi kết luận.",
        "- Nội dung nhạy cảm phải được hạn chế và kiểm duyệt trước khi kết nối dịch vụ thật.", ""])
    md = output/"triage_report.md"
    js = output/"triage_report.json"
    md.write_text("\n".join(lines), encoding="utf-8")
    js.write_text(json.dumps({"mode":mode,"generated_at":now,"items":results},indent=2,ensure_ascii=False),encoding="utf-8")
    return md,js
