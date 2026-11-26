"""Generate the synthetic loan-application PDFs used by the demo.

Every person, ID number, employer and amount below is invented. Each page carries a
"DỮ LIỆU GIẢ LẬP" banner so the files cannot be mistaken for real documents.

Usage (needs reportlab and a TTF font with Vietnamese glyphs, e.g. DejaVuSans):
    python scripts/generate_samples.py [--font /path/to/DejaVuSans.ttf]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from reportlab.lib.colors import Color, black
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"
DEFAULT_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
]

CASES = [
    {
        "case_id": "HS-001",
        "title": "Hồ sơ đầy đủ, thu nhập tốt",
        "expected_hint": "Đủ điều kiện",
        "person": {
            "name": "Nguyễn Văn An",
            "name_ascii": "NGUYEN VAN AN",
            "id": "079090000001",
            "dob": "15/03/1990",
            "expiry": "15/03/2030",
            "address": "12 Đường Số 7, Phường An Khánh, TP. Hồ Chí Minh",
        },
        "application": {"id": "079090000001", "amount": 120_000_000, "term": 36,
                        "purpose": "Sửa chữa nhà", "existing_debt": 2_000_000},
        "contract": {"employer": "Công ty TNHH Phần mềm Sao Mai (giả lập)",
                     "type": "Không xác định thời hạn", "start": "01/06/2021",
                     "end": None, "salary": 25_000_000, "id": "079090000001"},
        "statement": {"account": "0011 2233 4401", "id": "079090000001",
                      "salary": [("25/08/2026", 24_800_000, "CTY SAO MAI TRA LUONG T08/2026"),
                                 ("25/09/2026", 25_000_000, "CTY SAO MAI TRA LUONG T09/2026"),
                                 ("24/10/2026", 25_000_000, "CTY SAO MAI TRA LUONG T10/2026")]},
    },
    {
        "case_id": "HS-002",
        "title": "Thu nhập cao nhưng nghĩa vụ nợ lớn",
        "expected_hint": "Không đủ điều kiện",
        "person": {
            "name": "Trần Thị Bình",
            "name_ascii": "TRAN THI BINH",
            "id": "001185000002",
            "dob": "20/07/1985",
            "expiry": "20/07/2030",
            "address": "45 Phố Hoa Sữa, Phường Láng, Hà Nội",
        },
        "application": {"id": "001185000002", "amount": 300_000_000, "term": 48,
                        "purpose": "Mua sắm đồ dùng gia đình", "existing_debt": 9_000_000},
        "contract": {"employer": "Công ty Cổ phần Thương mại Hồng Hà (giả lập)",
                     "type": "Không xác định thời hạn", "start": "10/01/2019",
                     "end": None, "salary": 30_000_000, "id": "001185000002"},
        "statement": {"account": "0011 2233 4402", "id": "001185000002",
                      "salary": [("05/09/2026", 30_000_000, "HONG HA CHI LUONG THANG 08"),
                                 ("05/10/2026", 30_000_000, "HONG HA CHI LUONG THANG 09"),
                                 ("05/11/2026", 30_000_000, "HONG HA CHI LUONG THANG 10")]},
    },
    {
        "case_id": "HS-003",
        "title": "Sao kê thiếu kỳ lương, số CCCD không khớp",
        "expected_hint": "Cần bổ sung hồ sơ",
        "person": {
            "name": "Lê Hoàng Cường",
            "name_ascii": "LE HOANG CUONG",
            "id": "079095000003",
            "dob": "02/11/1995",
            "expiry": "02/11/2035",
            "address": "88 Đường Ven Sông, Phường Bình Đông, TP. Hồ Chí Minh",
        },
        "application": {"id": "079095000083", "amount": 60_000_000, "term": 24,
                        "purpose": "Học phí", "existing_debt": 0},
        "contract": {"employer": "Công ty TNHH Logistics Bến Nghé (giả lập)",
                     "type": "Xác định thời hạn 24 tháng", "start": "01/09/2025",
                     "end": "31/08/2027", "salary": 15_000_000, "id": "079095000003"},
        "statement": {"account": "0011 2233 4403", "id": "079095000003",
                      "salary": [("30/09/2026", 15_000_000, "BEN NGHE LOGISTICS LUONG T09"),
                                 ("31/10/2026", 15_000_000, "BEN NGHE LOGISTICS LUONG T10")]},
    },
    {
        "case_id": "HS-004",
        "title": "Quá tuổi và số tiền vay vượt hạn mức",
        "expected_hint": "Không đủ điều kiện",
        "person": {
            "name": "Phạm Minh Dũng",
            "name_ascii": "PHAM MINH DUNG",
            "id": "036065000004",
            "dob": "10/05/1965",
            "expiry": "Không thời hạn",
            "address": "7 Đường Trần Phú, Phường Nam Định, Ninh Bình",
        },
        "application": {"id": "036065000004", "amount": 250_000_000, "term": 60,
                        "purpose": "Du lịch", "existing_debt": 0},
        "contract": {"employer": "Công ty Cổ phần Dệt may Thành Nam (giả lập)",
                     "type": "Không xác định thời hạn", "start": "15/03/2010",
                     "end": None, "salary": 18_000_000, "id": "036065000004"},
        "statement": {"account": "0011 2233 4404", "id": "036065000004",
                      "salary": [("10/09/2026", 18_000_000, "THANH NAM TRA LUONG T08"),
                                 ("10/10/2026", 18_000_000, "THANH NAM TRA LUONG T09"),
                                 ("10/11/2026", 18_000_000, "THANH NAM TRA LUONG T10")]},
    },
]

OTHER_TXNS = [
    ("02/09/2026", -1_250_000, "THANH TOAN THE TIN DUNG"),
    ("12/09/2026", -650_000, "TT HOA DON DIEN EVN"),
    ("18/09/2026", 2_000_000, "NHAN CK TU NGUYEN THI HOA"),
    ("03/10/2026", -3_400_000, "CHUYEN TIEN NHA"),
    ("15/10/2026", -890_000, "MUA SAM ONLINE"),
    ("06/11/2026", -1_100_000, "TT HOA DON INTERNET + DIEN"),
]


def money(value: int) -> str:
    return f"{value:,.0f}".replace(",", ".")


class Doc:
    def __init__(self, path: Path, font: str):
        self.c = canvas.Canvas(str(path), pagesize=A4)
        self.font = font
        self.y = 800

    def banner(self) -> None:
        self.c.setFillColor(Color(0.8, 0.1, 0.1))
        self.c.setFont(self.font, 9)
        self.c.drawString(40, 820, "MẪU — DỮ LIỆU GIẢ LẬP CHO DEMO, KHÔNG PHẢI GIẤY TỜ THẬT")
        self.c.setFillColor(black)

    def title(self, text: str) -> None:
        self.banner()
        self.c.setFont(self.font, 15)
        self.c.drawString(40, self.y - 20, text)
        self.y -= 55

    def line(self, text: str, size: int = 11, gap: int = 20) -> None:
        if self.y < 60:
            self.c.showPage()
            self.banner()
            self.y = 790
        self.c.setFont(self.font, size)
        self.c.drawString(40, self.y, text)
        self.y -= gap

    def save(self) -> None:
        self.c.save()


def build_case(case: dict, font: str) -> None:
    folder = SAMPLES / case["case_id"].lower()
    folder.mkdir(parents=True, exist_ok=True)
    p, app, ct, st = case["person"], case["application"], case["contract"], case["statement"]

    doc = Doc(folder / "01_cccd.pdf", font)
    doc.title("CĂN CƯỚC CÔNG DÂN")
    doc.line("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM (bản mô phỏng)")
    doc.line(f"Số định danh cá nhân: {p['id']}")
    doc.line(f"Họ và tên: {p['name']}")
    doc.line(f"Ngày sinh: {p['dob']}")
    doc.line("Quốc tịch: Việt Nam")
    doc.line(f"Nơi thường trú: {p['address']}")
    doc.line(f"Có giá trị đến: {p['expiry']}")
    doc.save()

    doc = Doc(folder / "02_giay_de_nghi_vay.pdf", font)
    doc.title("GIẤY ĐỀ NGHỊ VAY VỐN KIÊM PHƯƠNG ÁN TRẢ NỢ")
    doc.line("Kính gửi: Ngân hàng Demo (giả lập)")
    doc.line(f"Họ và tên khách hàng: {p['name']}")
    doc.line(f"Số CCCD: {app['id']}")
    doc.line(f"Số tiền đề nghị vay: {money(app['amount'])} VND")
    doc.line(f"Thời hạn vay: {app['term']} tháng")
    doc.line(f"Mục đích vay: {app['purpose']}")
    doc.line(f"Nghĩa vụ trả nợ hiện tại hàng tháng: {money(app['existing_debt'])} VND")
    doc.line("Nguồn trả nợ: Lương hàng tháng")
    doc.line("Tôi cam kết các thông tin trên là đúng sự thật.")
    doc.line(f"Khách hàng ký tên: {p['name']}")
    doc.save()

    doc = Doc(folder / "03_hop_dong_lao_dong.pdf", font)
    doc.title("HỢP ĐỒNG LAO ĐỘNG")
    doc.line(f"Bên sử dụng lao động: {ct['employer']}")
    doc.line(f"Người lao động: {p['name']}")
    doc.line(f"Số CCCD: {ct['id']}")
    doc.line(f"Loại hợp đồng: {ct['type']}")
    doc.line(f"Ngày bắt đầu: {ct['start']}")
    if ct["end"]:
        doc.line(f"Ngày kết thúc: {ct['end']}")
    doc.line("Chức danh: Nhân viên")
    doc.line(f"Mức lương: {money(ct['salary'])} VND/tháng")
    doc.line("Hình thức trả lương: Chuyển khoản hàng tháng")
    doc.save()

    doc = Doc(folder / "04_sao_ke_tai_khoan.pdf", font)
    doc.title("SAO KÊ TÀI KHOẢN THANH TOÁN")
    doc.line(f"Chủ tài khoản: {p['name_ascii']}")
    doc.line(f"Số giấy tờ: {st['id']}")
    doc.line(f"Số tài khoản: {st['account']}")
    doc.line("Kỳ sao kê: 01/08/2026 - 20/11/2026")
    doc.line("Ngày | Nội dung | Số tiền (VND)", size=10)
    rows = [(d, a, t) for d, a, t in st["salary"]] + OTHER_TXNS
    rows.sort(key=lambda r: (r[0][6:], r[0][3:5], r[0][:2]))
    for date, amount, desc in rows:
        sign = "+" if amount > 0 else "-"
        doc.line(f"{date} | {desc} | {sign}{money(abs(amount))}", size=10, gap=16)
    doc.save()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--font", help="TTF font with Vietnamese glyphs")
    args = parser.parse_args()
    font_path = args.font or next((f for f in DEFAULT_FONTS if Path(f).exists()), None)
    if not font_path:
        raise SystemExit("No Vietnamese-capable TTF font found; pass --font")
    pdfmetrics.registerFont(TTFont("VN", font_path))
    for case in CASES:
        build_case(case, "VN")
    index = [{"case_id": c["case_id"], "applicant": c["person"]["name"], "title": c["title"],
              "folder": c["case_id"].lower()} for c in CASES]
    (SAMPLES / "cases.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n",
                                        encoding="utf-8")
    print(f"Generated {len(CASES)} cases in {SAMPLES}")


if __name__ == "__main__":
    main()
