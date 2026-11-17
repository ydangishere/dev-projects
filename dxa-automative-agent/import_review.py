"""
Nạp kết quả thợ duyệt từ bảng "DXA – Duyệt 53 case sửa xe" vào kho tri thức.

Cách dùng:
  1. Trong trang Sheet, tải về dạng .xlsx (hoặc .csv).
  2. python import_review.py duyet_case.xlsx
  3. python dxa.py build && python validate.py && python eval.py

Quy tắc:
  Đúng      -> reviewed = true
  Cần sửa   -> reviewed = false, lưu ghi chú của thợ vào review_note để sửa case
  Sai       -> status = "rejected": build bỏ case này ra khỏi kho, không xoá khỏi file
  Chưa duyệt-> giữ nguyên
"""
import csv, json, sys
from pathlib import Path

DATA = Path(__file__).parent / "data"
VALID = {"Chưa duyệt", "Đúng", "Cần sửa", "Sai"}

def read_rows(path):
    p = Path(path)
    if p.suffix.lower() == ".csv":
        rows = list(csv.reader(p.open(encoding="utf-8-sig")))
    else:
        from openpyxl import load_workbook
        ws = load_workbook(p, data_only=True).worksheets[0]
        rows = [[("" if c is None else str(c)) for c in r] for r in ws.iter_rows(values_only=True)]
    head_i = next(i for i, r in enumerate(rows) if r and r[0] == "ID")
    head = rows[head_i]
    col = {name: head.index(name) for name in ("ID", "Kết quả duyệt", "Ghi chú của thợ")}
    for r in rows[head_i + 1:]:
        if r and r[col["ID"]]:
            yield r[col["ID"]].strip(), r[col["Kết quả duyệt"]].strip(), r[col["Ghi chú của thợ"]].strip()

def main(path):
    review = {}
    for cid, verdict, note in read_rows(path):
        if verdict not in VALID:
            sys.exit(f"{cid}: kết quả duyệt '{verdict}' không hợp lệ")
        review[cid] = (verdict, note)

    counts = {k: 0 for k in VALID}
    seen = set()
    for f in sorted(DATA.glob("knowledge*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for c in d["cases"]:
            if c["id"] not in review:
                continue
            seen.add(c["id"])
            verdict, note = review[c["id"]]
            counts[verdict] += 1
            if verdict == "Chưa duyệt":
                continue
            c["reviewed"] = verdict == "Đúng"
            c["status"] = "rejected" if verdict == "Sai" else "active"
            if note:
                c["review_note"] = note
        f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")

    missing = set(review) - seen
    print(" | ".join(f"{k}: {v}" for k, v in counts.items()))
    if missing:
        print("Có trong bảng mà không có trong kho:", sorted(missing))
    need_fix = [cid for cid, (v, _) in review.items() if v == "Cần sửa"]
    if need_fix:
        print("Case cần sửa theo ghi chú của thợ:", need_fix)

if __name__ == "__main__":
    main(sys.argv[1])
