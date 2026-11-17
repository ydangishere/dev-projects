"""Kiểm agent Dana trên dữ liệu thật.

  python test_dana.py          chế độ có sẵn trong môi trường (mock / offline / Gemini thật)
In ra từng câu, cuối cùng in KẾT QUẢ: ĐẠT hoặc lỗi (exit 1).
"""
import sys

import dxa_dana

CASES = [  # (câu hỏi, case phải đứng đầu nguồn)
    ("Bình xăng con chảy xăng khi dựng xe", "C02"),
    ("buông ga mà ga không về", "C28"),
    ("Côn bị trượt", "C40"),
]
OUT = ["thay nhớt bao lâu một lần", "lốp xe bị xì"]

fails = []
for q, want in CASES:
    r = dxa_dana.ask(q)
    top = next((s["id"] for s in r["sources"] if s["type"] == "case"), None)
    print(f"--- {q}\n{r['answer']}\n[mode={r['mode']} by={r['answered_by']} top={top}] {r['warnings']}")
    if r["answered_by"].startswith("python"):
        fails.append(f"{q}: agent Dana không chạy ({r['warnings']})")
    if r["refused"] or top != want:
        fails.append(f"{q}: cần {want}, ra {top} refused={r['refused']}")
for q in OUT:
    r = dxa_dana.ask(q)
    print(f"--- {q}\n{r['answer']}\n[mode={r['mode']} by={r['answered_by']}]")
    if r["answered_by"].startswith("python"):
        fails.append(f"{q}: agent Dana không chạy ({r['warnings']})")
    if not r["refused"]:
        fails.append(f"{q}: lẽ ra phải từ chối")

print("\nKẾT QUẢ:", "ĐẠT" if not fails else "LỖI")
for f in fails:
    print(" -", f)
sys.exit(1 if fails else 0)
