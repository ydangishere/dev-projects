"""Simulated core-banking service.

In a real bank this logic lives in the core system (e.g. Temenos T24) behind Java
services and an integration layer. Here it is an in-memory stand-in with the same
kind of contract: read balance and history, create a pending transfer, and confirm it
only with a one-time password (OTP). All customers, accounts and amounts are invented.
"""

from __future__ import annotations

import random
import secrets
import threading
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from .textutil import mask_account, now_vn

PER_TRANSFER_LIMIT = 50_000_000
DAILY_TRANSFER_LIMIT = 100_000_000
OTP_TTL = timedelta(minutes=3)
MAX_OTP_ATTEMPTS = 3

CATEGORIES = {
    "an_uong": "Ăn uống",
    "mua_sam": "Mua sắm",
    "di_chuyen": "Di chuyển",
    "hoa_don": "Hóa đơn",
    "giai_tri": "Giải trí",
    "chuyen_khoan": "Chuyển khoản",
    "thu_nhap": "Thu nhập",
}

_MERCHANTS = {
    "an_uong": [("Highlands Coffee", 45_000, 95_000), ("GrabFood", 80_000, 350_000),
                ("Phở Bát Đàn", 60_000, 120_000), ("ShopeeFood", 70_000, 280_000), ("Bếp nhà Mây", 150_000, 650_000)],
    "mua_sam": [("Shopee", 120_000, 900_000), ("Tiki", 150_000, 1_200_000), ("Co.opmart", 300_000, 1_500_000)],
    "di_chuyen": [("Grab", 35_000, 180_000), ("Be", 30_000, 150_000), ("Xăng Petrolimex", 80_000, 120_000)],
    "giai_tri": [("CGV Cinemas", 90_000, 260_000), ("Spotify", 59_000, 59_000)],
}
_BILLS = [("EVN điện", 650_000, 950_000), ("Nước sinh hoạt", 120_000, 220_000), ("Internet VNPT", 240_000, 240_000)]


class CoreError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class Beneficiary:
    beneficiary_id: str
    name: str
    bank: str
    account: str
    aliases: list[str]

    def public(self) -> dict:
        return {"beneficiary_id": self.beneficiary_id, "name": self.name, "bank": self.bank,
                "account_masked": mask_account(self.account), "aliases": self.aliases}


@dataclass
class Transaction:
    txn_id: str
    posted_at: datetime
    amount: int            # negative = debit
    description: str
    category: str

    def public(self) -> dict:
        return {"txn_id": self.txn_id, "posted_at": self.posted_at.isoformat(timespec="minutes"),
                "amount": self.amount, "description": self.description, "category": self.category,
                "category_label": CATEGORIES.get(self.category, self.category)}


@dataclass
class Transfer:
    transfer_id: str
    account_id: str
    beneficiary: Beneficiary
    amount: int
    note: str
    otp: str
    created_at: datetime
    expires_at: datetime
    status: str = "PENDING_OTP"   # PENDING_OTP | COMPLETED | EXPIRED | LOCKED | CANCELLED
    attempts: int = 0
    completed_at: datetime | None = None

    def public(self) -> dict:
        return {"transfer_id": self.transfer_id, "amount": self.amount, "note": self.note,
                "beneficiary": self.beneficiary.public(), "status": self.status,
                "expires_at": self.expires_at.isoformat(timespec="seconds"),
                "attempts_left": MAX_OTP_ATTEMPTS - self.attempts}


@dataclass
class Account:
    account_id: str
    customer_id: str
    holder: str
    number: str
    opening_balance: int
    transactions: list[Transaction] = field(default_factory=list)

    @property
    def balance(self) -> int:
        return self.opening_balance + sum(t.amount for t in self.transactions)


def _month_starts(anchor: date, count: int) -> list[date]:
    starts, year, month = [], anchor.year, anchor.month
    for _ in range(count):
        starts.append(date(year, month, 1))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return list(reversed(starts))


def seed_transactions(anchor: datetime, seed: int = 7) -> list[Transaction]:
    """Three months of plausible card/bill/salary activity ending at `anchor`."""
    rng = random.Random(seed)
    tz = anchor.tzinfo
    txns: list[Transaction] = []

    def add(day: date, hour: int, amount: int, description: str, category: str) -> None:
        moment = datetime(day.year, day.month, day.day, hour, rng.randint(0, 59), tzinfo=tz)
        if moment <= anchor:
            txns.append(Transaction(f"T{len(txns) + 1:04d}", moment, amount, description, category))

    for start in _month_starts(anchor.date(), 3):
        last_day = (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        add(start.replace(day=5), 9, 25_000_000, "CTY SAO MAI TRA LUONG", "thu_nhap")
        add(start.replace(day=8), 20, -3_000_000, "Chuyển khoản cho Trần Thị Mai", "chuyen_khoan")
        for name, low, high in _BILLS:
            add(start.replace(day=rng.randint(10, 15)), 10, -rng.randrange(low, high + 1, 1000), name, "hoa_don")
        for category, count in (("an_uong", 14), ("mua_sam", 4), ("di_chuyen", 9), ("giai_tri", 2)):
            for _ in range(count):
                name, low, high = rng.choice(_MERCHANTS[category])
                amount = rng.randrange(low, high + 1, 1000)
                add(start.replace(day=rng.randint(1, last_day.day)), rng.randint(7, 22), -amount, name, category)
    txns.sort(key=lambda t: t.posted_at)
    for index, txn in enumerate(txns, start=1):
        txn.txn_id = f"T{index:04d}"
    return txns


class CoreBankingService:
    """Thread-safe in-memory core. `clock` is injectable so tests can control time."""

    def __init__(self, clock=now_vn, anchor: datetime | None = None, show_demo_otp: bool = True):
        self.clock = clock
        self.show_demo_otp = show_demo_otp
        self._lock = threading.Lock()
        anchor = anchor or clock()
        self.customer = {"customer_id": "C001", "name": "Nguyễn Văn An"}
        self.accounts = {
            "A001": Account("A001", "C001", "NGUYEN VAN AN", "0011 2233 4401", 12_500_000,
                            seed_transactions(anchor)),
        }
        self.beneficiaries = {
            "B01": Beneficiary("B01", "Trần Thị Mai", "Vietcombank", "9988 7766 5501", ["mẹ", "má", "mai"]),
            "B02": Beneficiary("B02", "Nguyễn Thị Lan", "Techcombank", "1903 4455 6602", ["lan", "chị lan"]),
            "B03": Beneficiary("B03", "Lê Văn Hùng", "MB Bank", "0868 1122 3303", ["hùng", "anh hùng"]),
            "B04": Beneficiary("B04", "Phạm Thu Trang", "VPBank", "2207 8899 0004", ["trang"]),
        }
        self.transfers: dict[str, Transfer] = {}

    # ---- reads -----------------------------------------------------------------------
    def _account(self, account_id: str) -> Account:
        if account_id not in self.accounts:
            raise CoreError("ACCOUNT_NOT_FOUND", "Không tìm thấy tài khoản")
        return self.accounts[account_id]

    def get_balance(self, account_id: str) -> dict:
        account = self._account(account_id)
        return {"account_id": account_id, "account_masked": mask_account(account.number),
                "holder": account.holder, "available_balance": account.balance, "currency": "VND",
                "as_of": self.clock().isoformat(timespec="minutes")}

    def list_transactions(self, account_id: str, start: datetime | None = None, end: datetime | None = None,
                          category: str | None = None, limit: int | None = None) -> list[dict]:
        account = self._account(account_id)
        items = [t for t in account.transactions
                 if (start is None or t.posted_at >= start) and (end is None or t.posted_at < end)
                 and (category is None or t.category == category)]
        items.sort(key=lambda t: t.posted_at, reverse=True)
        return [t.public() for t in (items[:limit] if limit else items)]

    def list_beneficiaries(self, customer_id: str) -> list[dict]:
        if customer_id != self.customer["customer_id"]:
            raise CoreError("CUSTOMER_NOT_FOUND", "Không tìm thấy khách hàng")
        return [b.public() for b in self.beneficiaries.values()]

    # ---- transfers ---------------------------------------------------------------------
    def _sent_today(self, account: Account) -> int:
        today = self.clock().date()
        return -sum(t.amount for t in account.transactions
                    if t.category == "chuyen_khoan" and t.posted_at.date() == today)

    def create_transfer(self, account_id: str, beneficiary_id: str, amount: int, note: str = "") -> dict:
        with self._lock:
            account = self._account(account_id)
            beneficiary = self.beneficiaries.get(beneficiary_id)
            if not beneficiary:
                raise CoreError("BENEFICIARY_NOT_FOUND", "Người nhận chưa có trong danh bạ")
            if not isinstance(amount, int) or amount < 10_000:
                raise CoreError("INVALID_AMOUNT", "Số tiền chuyển tối thiểu là 10.000 ₫")
            if amount > PER_TRANSFER_LIMIT:
                raise CoreError("OVER_TRANSFER_LIMIT", "Vượt hạn mức 50.000.000 ₫ cho mỗi giao dịch")
            if self._sent_today(account) + amount > DAILY_TRANSFER_LIMIT:
                raise CoreError("OVER_DAILY_LIMIT", "Vượt hạn mức chuyển tiền trong ngày 100.000.000 ₫")
            if amount > account.balance:
                raise CoreError("INSUFFICIENT_FUNDS", "Số dư không đủ để thực hiện giao dịch")
            now = self.clock()
            transfer = Transfer(uuid.uuid4().hex[:10], account_id, beneficiary, amount, note[:120],
                                f"{secrets.randbelow(1_000_000):06d}", now, now + OTP_TTL)
            self.transfers[transfer.transfer_id] = transfer
            result = transfer.public()
            if self.show_demo_otp:
                result["demo_otp"] = transfer.otp  # stands in for the SMS; never shown in chat text
            return result

    def confirm_transfer(self, transfer_id: str, otp: str) -> dict:
        with self._lock:
            transfer = self.transfers.get(transfer_id)
            if not transfer:
                raise CoreError("TRANSFER_NOT_FOUND", "Không tìm thấy lệnh chuyển")
            if transfer.status == "COMPLETED":
                return transfer.public()  # idempotent: confirming twice does not debit twice
            if transfer.status != "PENDING_OTP":
                raise CoreError(f"TRANSFER_{transfer.status}", "Lệnh chuyển không còn hiệu lực")
            now = self.clock()
            if now > transfer.expires_at:
                transfer.status = "EXPIRED"
                raise CoreError("OTP_EXPIRED", "Mã OTP đã hết hạn, vui lòng tạo lệnh mới")
            if not secrets.compare_digest(str(otp).strip(), transfer.otp):
                transfer.attempts += 1
                if transfer.attempts >= MAX_OTP_ATTEMPTS:
                    transfer.status = "LOCKED"
                    raise CoreError("OTP_LOCKED", "Nhập sai OTP quá 3 lần, lệnh chuyển đã bị khóa")
                raise CoreError("OTP_INVALID", f"Mã OTP không đúng, còn {MAX_OTP_ATTEMPTS - transfer.attempts} lần thử")
            account = self._account(transfer.account_id)
            if transfer.amount > account.balance:
                transfer.status = "CANCELLED"
                raise CoreError("INSUFFICIENT_FUNDS", "Số dư không đủ để thực hiện giao dịch")
            account.transactions.append(Transaction(
                f"T{len(account.transactions) + 1:04d}", now, -transfer.amount,
                f"Chuyển khoản cho {transfer.beneficiary.name}", "chuyen_khoan"))
            transfer.status = "COMPLETED"
            transfer.completed_at = now
            return {**transfer.public(), "new_balance": account.balance}

    def cancel_transfer(self, transfer_id: str) -> dict:
        with self._lock:
            transfer = self.transfers.get(transfer_id)
            if not transfer:
                raise CoreError("TRANSFER_NOT_FOUND", "Không tìm thấy lệnh chuyển")
            if transfer.status == "PENDING_OTP":
                transfer.status = "CANCELLED"
            return transfer.public()
