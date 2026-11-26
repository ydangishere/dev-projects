"""The assistant: guardrails → intent → tool call → templated answer, with a trace.

Every number shown to the customer comes from a core-banking tool result and is put
into a fixed Vietnamese template. The LLM (optional) is used only to understand
messages the rule parser cannot classify; it never writes amounts or balances.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from . import guardrails, nlu
from .audit import AuditLog
from .core_bank import CATEGORIES, CoreError
from .core_client import CoreClient
from .llm import LLMConfig
from .llm_nlu import parse_with_llm
from .nlu import Intent
from .textutil import fmt_vnd, now_vn

SUGGESTIONS = ["Số dư của tôi", "Tháng này tôi tiêu bao nhiêu?", "Chi ăn uống tháng trước",
               "5 giao dịch gần nhất", "Chuyển 500k cho mẹ"]
SESSION_TTL = timedelta(minutes=30)


@dataclass
class Session:
    session_id: str
    updated_at: datetime
    pending: dict | None = None            # transfer slots collected so far
    open_transfer_id: str | None = None


@dataclass
class Turn:
    reply: str
    cards: list[dict] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    intent: dict | None = None
    trace: list[dict] = field(default_factory=list)
    blocked: str | None = None

    def to_dict(self) -> dict:
        return self.__dict__.copy()


class Assistant:
    def __init__(self, core: CoreClient, audit: AuditLog, llm: LLMConfig | None = None,
                 customer_id: str = "C001", account_id: str = "A001", clock=now_vn):
        self.core = core
        self.audit = audit
        self.llm = llm or LLMConfig()
        self.customer_id = customer_id
        self.account_id = account_id
        self.clock = clock
        self.sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    # ---- helpers ---------------------------------------------------------------------
    def _session(self, session_id: str) -> Session:
        now = self.clock()
        with self._lock:
            for key in [k for k, s in self.sessions.items() if now - s.updated_at > SESSION_TTL]:
                del self.sessions[key]
            session = self.sessions.setdefault(session_id, Session(session_id, now))
            session.updated_at = now
            return session

    def _tool(self, trace: list[dict], name: str, func, *args, **kwargs):
        started = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            trace.append({"step": "tool", "name": name, "ok": True,
                          "ms": round((time.perf_counter() - started) * 1000, 1)})
            return result
        except CoreError as exc:
            trace.append({"step": "tool", "name": name, "ok": False, "error": exc.code,
                          "ms": round((time.perf_counter() - started) * 1000, 1)})
            raise

    def period_range(self, slots: dict) -> tuple[datetime, datetime, str]:
        now = self.clock()
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = midnight.replace(day=1)
        period = slots.get("period", "this_month")
        if period == "last_month":
            start = (month_start - timedelta(days=1)).replace(day=1)
            return start, month_start, f"tháng {start.month:02d}/{start.year}"
        if period == "month":
            month = slots["month"]
            year = slots.get("year") or (now.year if month <= now.month else now.year - 1)
            start = month_start.replace(year=year, month=month)
            end = (start + timedelta(days=32)).replace(day=1)
            return start, min(end, now + timedelta(seconds=1)), f"tháng {month:02d}/{year}"
        if period == "this_week":
            return midnight - timedelta(days=now.weekday()), now + timedelta(seconds=1), "tuần này"
        if period == "last_7_days":
            return now - timedelta(days=7), now + timedelta(seconds=1), "7 ngày qua"
        if period == "today":
            return midnight, now + timedelta(seconds=1), "hôm nay"
        if period == "yesterday":
            return midnight - timedelta(days=1), midnight, "hôm qua"
        return month_start, now + timedelta(seconds=1), f"tháng {now.month:02d}/{now.year}"

    # ---- entry point -----------------------------------------------------------------
    def handle(self, session_id: str, message: str) -> dict:
        session = self._session(session_id)
        trace: list[dict] = []
        check = guardrails.check(message)
        trace.append({"step": "guardrail", "allowed": check.allowed, "category": check.category})
        if not check.allowed:
            turn = Turn(check.message or "", suggestions=SUGGESTIONS[:3], trace=trace, blocked=check.category)
            self._log(session, message, turn, security=check.security_event)
            return turn.to_dict()

        try:
            beneficiaries = self._tool(trace, "list_beneficiaries", self.core.list_beneficiaries, self.customer_id)
            intent = nlu.parse(message, beneficiaries)
            if self.llm.enabled and self._needs_llm(intent, session):
                intent = parse_with_llm(self.llm, message, beneficiaries) or intent
            trace.append({"step": "understand", **intent.to_dict()})
            turn = self._dispatch(session, intent, beneficiaries, trace)
        except CoreError as exc:
            turn = Turn(f"Xin lỗi, hệ thống ngân hàng báo lỗi: {exc.message}.", trace=trace)
        turn.trace = trace
        self._log(session, message, turn)
        return turn.to_dict()

    @staticmethod
    def _needs_llm(intent: Intent, session: Session) -> bool:
        """Ask the model only when the rules could not understand the message."""
        if intent.name == "unknown":
            return True
        slots = intent.slots
        return (intent.name == "fragment" and session.pending is None
                and not (slots.get("amount") and slots.get("beneficiary_ids")))

    def _log(self, session: Session, message: str, turn: Turn, security: bool = False) -> None:
        self.audit.write("security_event" if security else "chat", {
            "session": session.session_id[:8],
            "message": guardrails.mask_for_log(message)[:200],
            "intent": turn.intent,
            "blocked": turn.blocked,
            "tools": [t["name"] for t in turn.trace if t["step"] == "tool"],
            "transfer_prepared": any(c["type"] == "transfer_confirm" for c in turn.cards),
            "llm_provider": self.llm.provider,
        })

    # ---- handlers --------------------------------------------------------------------
    def _dispatch(self, session: Session, intent: Intent, beneficiaries: list[dict], trace: list[dict]) -> Turn:
        if intent.name == "fragment" and session.pending is None \
                and intent.slots.get("amount") and intent.slots.get("beneficiary_ids"):
            # "Gửi mẹ 1 triệu", "bắn cho Trang 200k": amount + saved contact reads as a transfer.
            # Safe because it only prepares a pending transfer that still needs the customer's OTP.
            intent = Intent("transfer", intent.slots, intent.source)
        if intent.name == "fragment":
            if session.pending is None:
                return Turn("Bạn muốn làm gì với thông tin này? Ví dụ: \"Chuyển 500k cho mẹ\".",
                            suggestions=SUGGESTIONS, intent=intent.to_dict())
            merged = {**session.pending}
            for key in ("amount", "amount_text"):
                if intent.slots.get(key):
                    merged[key] = intent.slots[key]
            if intent.slots.get("beneficiary_ids"):
                merged["beneficiary_ids"] = intent.slots["beneficiary_ids"]
                merged["mentioned_name"] = None
            intent = Intent("transfer", merged, intent.source)
        if intent.name != "transfer":
            session.pending = None
        handler = getattr(self, f"_on_{intent.name}", self._on_unknown)
        turn = handler(session, intent, beneficiaries, trace)
        turn.intent = intent.to_dict()
        return turn

    def _on_greeting(self, session, intent, beneficiaries, trace) -> Turn:
        return Turn("Xin chào! Mình là trợ lý ngân hàng (bản demo). Mình có thể xem số dư, thống kê chi tiêu, "
                    "liệt kê giao dịch và soạn lệnh chuyển tiền cho người trong danh bạ.", suggestions=SUGGESTIONS)

    _on_help = _on_greeting

    def _on_unknown(self, session, intent, beneficiaries, trace) -> Turn:
        return Turn("Mình chưa hiểu yêu cầu này. Mình hỗ trợ: xem số dư, chi tiêu theo tháng hoặc theo nhóm, "
                    "giao dịch gần đây, danh bạ người nhận và chuyển tiền.", suggestions=SUGGESTIONS)

    def _on_balance(self, session, intent, beneficiaries, trace) -> Turn:
        data = self._tool(trace, "get_balance", self.core.get_balance, self.account_id)
        stamp = datetime.fromisoformat(data["as_of"]).strftime("%H:%M %d/%m/%Y")
        return Turn(f"Số dư khả dụng tài khoản {data['account_masked']} là {fmt_vnd(data['available_balance'])} "
                    f"(cập nhật {stamp}).",
                    cards=[{"type": "balance", **data}], suggestions=["Tháng này tôi tiêu bao nhiêu?", "5 giao dịch gần nhất"])

    def _on_spending(self, session, intent, beneficiaries, trace) -> Turn:
        start, end, label = self.period_range(intent.slots)
        category = intent.slots.get("category")
        items = self._tool(trace, "list_transactions", self.core.list_transactions, self.account_id, start, end,
                           category)
        debits = [t for t in items if t["amount"] < 0 and t["category"] not in {"chuyen_khoan", "thu_nhap"}]
        total = -sum(t["amount"] for t in debits)
        if category:
            name = CATEGORIES[category].lower()
            if not debits:
                return Turn(f"{label.capitalize()} bạn chưa có khoản chi nào cho {name}.", intent=intent.to_dict())
            biggest = min(debits, key=lambda t: t["amount"])
            when = datetime.fromisoformat(biggest["posted_at"]).strftime("%d/%m")
            reply = (f"{label.capitalize()} bạn đã chi {fmt_vnd(total)} cho {name} ({len(debits)} giao dịch). "
                     f"Khoản lớn nhất: {fmt_vnd(-biggest['amount'])} tại {biggest['description']} ngày {when}.")
            return Turn(reply, cards=[{"type": "transactions", "title": f"Chi {name} {label}", "items": debits[:8]}],
                        suggestions=["Chi tiêu theo nhóm tháng này", "Số dư của tôi"])
        if not debits:
            return Turn(f"{label.capitalize()} bạn chưa có khoản chi tiêu nào.")
        groups: dict[str, int] = {}
        for t in debits:
            groups[t["category"]] = groups.get(t["category"], 0) - t["amount"]
        breakdown = [{"category": c, "label": CATEGORIES[c], "amount": a, "percent": round(a * 100 / total, 1)}
                     for c, a in sorted(groups.items(), key=lambda kv: kv[1], reverse=True)]
        top = breakdown[0]
        transfers_out = -sum(t["amount"] for t in items if t["category"] == "chuyen_khoan" and t["amount"] < 0)
        reply = (f"{label.capitalize()} bạn đã chi tiêu {fmt_vnd(total)} qua {len(debits)} giao dịch. "
                 f"Nhiều nhất là {top['label'].lower()}: {fmt_vnd(top['amount'])} ({top['percent']}%).")
        if transfers_out:
            reply += f" Ngoài ra bạn đã chuyển khoản {fmt_vnd(transfers_out)} (không tính vào chi tiêu)."
        return Turn(reply, cards=[{"type": "spending", "title": f"Chi tiêu {label}", "total": total,
                                   "breakdown": breakdown}],
                    suggestions=[f"Chi {b['label'].lower()} {label}" for b in breakdown[:2]])

    def _on_transactions(self, session, intent, beneficiaries, trace) -> Turn:
        limit = intent.slots.get("limit", 5)
        items = self._tool(trace, "list_transactions", self.core.list_transactions, self.account_id, limit=limit)
        return Turn(f"Đây là {len(items)} giao dịch gần nhất của bạn.",
                    cards=[{"type": "transactions", "title": "Giao dịch gần đây", "items": items}])

    def _on_beneficiaries(self, session, intent, beneficiaries, trace) -> Turn:
        return Turn(f"Danh bạ người nhận của bạn có {len(beneficiaries)} người.",
                    cards=[{"type": "beneficiaries", "items": beneficiaries}],
                    suggestions=[f"Chuyển 200k cho {b['aliases'][0]}" for b in beneficiaries[:2]])

    def _on_cancel(self, session, intent, beneficiaries, trace) -> Turn:
        session.pending = None
        if session.open_transfer_id:
            result = self._tool(trace, "cancel_transfer", self.core.cancel_transfer, session.open_transfer_id)
            session.open_transfer_id = None
            if result["status"] == "CANCELLED":
                return Turn("Đã hủy lệnh chuyển tiền đang chờ xác nhận. Không có khoản tiền nào bị trừ.")
        return Turn("Đã hủy yêu cầu. Bạn cần mình hỗ trợ gì khác?", suggestions=SUGGESTIONS[:3])

    def _on_transfer(self, session, intent, beneficiaries, trace) -> Turn:
        slots = intent.slots
        ids = slots.get("beneficiary_ids") or []
        by_id = {b["beneficiary_id"]: b for b in beneficiaries}
        if len(ids) > 1:
            session.pending = {**slots, "beneficiary_ids": []}
            names = ", ".join(by_id[i]["name"] for i in ids)
            return Turn(f"Bạn muốn chuyển cho ai: {names}?", suggestions=[f"cho {by_id[i]['aliases'][0]}" for i in ids])
        if not ids:
            session.pending = {**slots, "beneficiary_ids": []}
            contacts = [f"cho {b['aliases'][0]}" for b in beneficiaries]
            if slots.get("mentioned_name"):
                return Turn(f"Mình không tìm thấy \"{slots['mentioned_name']}\" trong danh bạ người nhận. "
                            "Vì an toàn, trợ lý chỉ chuyển cho người đã lưu sẵn. Bạn muốn chuyển cho ai trong danh bạ?",
                            cards=[{"type": "beneficiaries", "items": beneficiaries}], suggestions=contacts)
            return Turn("Bạn muốn chuyển cho ai?", cards=[{"type": "beneficiaries", "items": beneficiaries}],
                        suggestions=contacts)
        beneficiary = by_id[ids[0]]
        if not slots.get("amount"):
            session.pending = {**slots}
            return Turn(f"Bạn muốn chuyển bao nhiêu cho {beneficiary['name']}?",
                        suggestions=["200k", "500k", "1 triệu"])
        if session.open_transfer_id:  # only one pending transfer per conversation
            self._tool(trace, "cancel_transfer", self.core.cancel_transfer, session.open_transfer_id)
            session.open_transfer_id = None
        try:
            transfer = self._tool(trace, "create_transfer", self.core.create_transfer, self.account_id,
                                  beneficiary["beneficiary_id"], int(slots["amount"]), "Chuyển tiền qua trợ lý")
        except CoreError as exc:
            session.pending = None
            return Turn(f"Mình chưa thể tạo lệnh chuyển: {exc.message}.", suggestions=["Số dư của tôi"])
        session.pending = None
        session.open_transfer_id = transfer["transfer_id"]
        b = transfer["beneficiary"]
        reply = (f"Mình đã soạn lệnh chuyển {fmt_vnd(transfer['amount'])} cho {b['name']} ({b['bank']} "
                 f"{b['account_masked']}). Lệnh CHƯA được thực hiện: bạn hãy kiểm tra lại và nhập mã OTP "
                 "vào ô xác nhận bên dưới.")
        return Turn(reply, cards=[{"type": "transfer_confirm", "transfer": transfer}])
