"""Deterministic credit rules. Each rule cites the policy clause it enforces.

Numbers and pass/fail outcomes are computed here, never by the language model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .extraction import INDEFINITE, Evidence, Extraction
from .textutil import add_months, fmt_date, fmt_vnd, months_between, norm, years_between

PASS, FAIL, NEED_INFO = "PASS", "FAIL", "NEED_INFO"

MIN_INCOME = 8_000_000
MAX_AMOUNT = 500_000_000
INCOME_MULTIPLE = 12
MAX_DTI = 0.50
REFERENCE_RATE = 0.14
MIN_AGE, MAX_AGE, MAX_AGE_AT_MATURITY = 20, 60, 65
MIN_TENURE_MONTHS = 12
MIN_FIXED_TERM_REMAINING = 6
SALARY_MONTHS = 3
MAX_DAYS_SINCE_LAST_SALARY = 45

VERDICTS = {
    "APPROVE": "Đủ điều kiện — đề xuất phê duyệt",
    "NEED_INFO": "Cần bổ sung hồ sơ",
    "REJECT": "Không đủ điều kiện — đề xuất từ chối",
}
REQUIRED_DOCS = ["cccd", "loan_application", "labor_contract", "bank_statement"]


@dataclass
class RuleResult:
    rule_id: str
    title: str
    clause_id: str
    status: str
    detail: str
    evidence: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class Facts:
    """Values computed from the extraction and used by several rules."""

    as_of: date
    salary_months: list[tuple[int, int]]
    latest_salaries: list[int]
    average_salary: float | None
    contract_salary: int | None
    income: float | None
    installment: float | None
    existing_debt: int | None
    dti: float | None

    def to_dict(self) -> dict:
        return {
            "as_of": self.as_of.isoformat(),
            "latest_salaries": self.latest_salaries,
            "average_salary": round(self.average_salary) if self.average_salary else None,
            "contract_salary": self.contract_salary,
            "income_for_assessment": round(self.income) if self.income else None,
            "estimated_installment": round(self.installment) if self.installment else None,
            "existing_monthly_debt": self.existing_debt,
            "dti_percent": round(self.dti * 100, 1) if self.dti is not None else None,
        }


def annuity_payment(principal: float, months: int, annual_rate: float = REFERENCE_RATE) -> float:
    rate = annual_rate / 12
    return principal * rate / (1 - (1 + rate) ** -months)


def _ev(*items: Evidence | None) -> list[dict]:
    return [item.to_dict() for item in items if item is not None]


def compute_facts(ex: Extraction, as_of: date) -> Facts:
    by_month: dict[tuple[int, int], int] = {}
    for credit in ex.salary_credits:
        key = (credit.date.year, credit.date.month)
        by_month[key] = by_month.get(key, 0) + credit.amount
    months = sorted(by_month)[-SALARY_MONTHS:]
    latest = [by_month[m] for m in months]
    average = sum(latest) / len(latest) if latest else None
    contract_salary = ex.value("labor_contract", "monthly_salary")
    candidates = [v for v in (contract_salary, average) if v]
    income = min(candidates) if candidates else None  # Điều 4.4: take the lower figure
    amount = ex.value("loan_application", "requested_amount")
    term = ex.value("loan_application", "term_months")
    existing = ex.value("loan_application", "existing_monthly_debt")
    installment = annuity_payment(amount, term) if amount and term else None
    dti = None
    if income and installment is not None and existing is not None:
        dti = (installment + existing) / income
    return Facts(as_of, months, latest, average, contract_salary, income, installment, existing, dti)


def _r_documents(ex: Extraction, facts: Facts) -> RuleResult:
    missing = [t for t in REQUIRED_DOCS if t not in ex.fields]
    labels = {"cccd": "CCCD", "loan_application": "Giấy đề nghị vay", "labor_contract": "Hợp đồng lao động",
              "bank_statement": "Sao kê lương"}
    if missing:
        return RuleResult("R01", "Đủ bộ hồ sơ bắt buộc", "Điều 2", NEED_INFO,
                          "Thiếu: " + ", ".join(labels[m] for m in missing))
    return RuleResult("R01", "Đủ bộ hồ sơ bắt buộc", "Điều 2", PASS, "Có đủ 4 loại giấy tờ")


def _r_age(ex: Extraction, facts: Facts) -> RuleResult:
    dob_ev = ex.get("cccd", "date_of_birth")
    term = ex.value("loan_application", "term_months")
    if not dob_ev or not term:
        return RuleResult("R02", "Độ tuổi", "3.1", NEED_INFO, "Thiếu ngày sinh hoặc thời hạn vay")
    age = years_between(dob_ev.value, facts.as_of)
    age_end = years_between(dob_ev.value, add_months(facts.as_of, term))
    ok = MIN_AGE <= age <= MAX_AGE and age_end <= MAX_AGE_AT_MATURITY
    detail = (f"Tuổi hiện tại {age}, tuổi khi kết thúc khoản vay {age_end} "
              f"(giới hạn {MIN_AGE}–{MAX_AGE}, tối đa {MAX_AGE_AT_MATURITY} khi tất toán)")
    return RuleResult("R02", "Độ tuổi", "3.1", PASS if ok else FAIL, detail,
                      _ev(dob_ev, ex.get("loan_application", "term_months")))


def _r_id_valid(ex: Extraction, facts: Facts) -> RuleResult:
    ev = ex.get("cccd", "expiry_date")
    if not ev:
        return RuleResult("R03", "CCCD còn hiệu lực", "3.2", NEED_INFO, "Không đọc được ngày hết hạn CCCD")
    if ev.value == INDEFINITE:
        return RuleResult("R03", "CCCD còn hiệu lực", "3.2", PASS, "CCCD không thời hạn", _ev(ev))
    if ev.value < facts.as_of:
        return RuleResult("R03", "CCCD còn hiệu lực", "3.2", NEED_INFO,
                          f"CCCD hết hạn ngày {fmt_date(ev.value)}, cần cập nhật giấy tờ", _ev(ev))
    return RuleResult("R03", "CCCD còn hiệu lực", "3.2", PASS, f"Hiệu lực đến {fmt_date(ev.value)}", _ev(ev))


def _r_consistency(ex: Extraction, facts: Facts) -> RuleResult:
    names = {dt: ex.get(dt, f) for dt, f in [("cccd", "full_name"), ("loan_application", "full_name"),
                                             ("labor_contract", "full_name"), ("bank_statement", "account_holder")]}
    ids = {dt: ex.get(dt, "id_number") for dt in REQUIRED_DOCS}
    problems = []
    reference_name = names["cccd"]
    reference_id = ids["cccd"]
    if not reference_name or not reference_id:
        return RuleResult("R04", "Thống nhất họ tên và số CCCD", "3.3", NEED_INFO,
                          "Thiếu họ tên hoặc số CCCD trên căn cước để đối chiếu")
    for ev in names.values():
        if ev and norm(ev.value) != norm(reference_name.value):
            problems.append(f"họ tên trên {ev.filename} là '{ev.value}'")
    for ev in ids.values():
        if ev and ev.value != reference_id.value:
            problems.append(f"số CCCD trên {ev.filename} kết thúc bằng ...{ev.value[-3:]}, "
                            f"căn cước kết thúc bằng ...{reference_id.value[-3:]}")
    evidence = _ev(*names.values(), *ids.values())
    if problems:
        return RuleResult("R04", "Thống nhất họ tên và số CCCD", "3.3", NEED_INFO,
                          "Cần xác minh: " + "; ".join(problems), evidence)
    return RuleResult("R04", "Thống nhất họ tên và số CCCD", "3.3", PASS,
                      "Họ tên và số CCCD khớp trên các giấy tờ đã đọc", evidence)


def _r_income(ex: Extraction, facts: Facts) -> RuleResult:
    if not facts.income:
        return RuleResult("R05", "Thu nhập tối thiểu", "4.1", NEED_INFO, "Không xác định được thu nhập")
    ok = facts.income >= MIN_INCOME
    detail = (f"Thu nhập dùng để xét duyệt {fmt_vnd(facts.income)} "
              f"(thấp hơn giữa lương hợp đồng {fmt_vnd(facts.contract_salary)} và bình quân sao kê "
              f"{fmt_vnd(facts.average_salary)}, theo Điều 4.4); yêu cầu tối thiểu {fmt_vnd(MIN_INCOME)}")
    return RuleResult("R05", "Thu nhập tối thiểu", "4.1", PASS if ok else FAIL, detail,
                      _ev(ex.get("labor_contract", "monthly_salary")))


def _r_salary_history(ex: Extraction, facts: Facts) -> RuleResult:
    credits = [c.to_dict() for c in ex.salary_credits]
    months = facts.salary_months
    if len(months) < SALARY_MONTHS:
        return RuleResult("R06", "3 tháng lương liên tiếp", "4.2", NEED_INFO,
                          f"Sao kê chỉ có {len(months)} kỳ lương; cần bổ sung sao kê đủ {SALARY_MONTHS} tháng", credits)
    consecutive = all((months[i + 1][0] * 12 + months[i + 1][1]) - (months[i][0] * 12 + months[i][1]) == 1
                      for i in range(len(months) - 1))
    last_credit = max(c.date for c in ex.salary_credits)
    recent = (facts.as_of - last_credit).days <= MAX_DAYS_SINCE_LAST_SALARY
    if not consecutive or not recent:
        reason = "các kỳ lương không liên tiếp" if not consecutive else \
            f"kỳ lương gần nhất ngày {fmt_date(last_credit)} đã quá {MAX_DAYS_SINCE_LAST_SALARY} ngày"
        return RuleResult("R06", "3 tháng lương liên tiếp", "4.2", NEED_INFO,
                          f"Cần bổ sung sao kê: {reason}", credits)
    detail = "Nhận lương các tháng " + ", ".join(f"{m:02d}/{y}" for y, m in months)
    return RuleResult("R06", "3 tháng lương liên tiếp", "4.2", PASS, detail, credits)


def _r_employment(ex: Extraction, facts: Facts) -> RuleResult:
    start = ex.get("labor_contract", "start_date")
    kind = ex.get("labor_contract", "contract_type")
    if not start or not kind:
        return RuleResult("R07", "Thâm niên và hợp đồng lao động", "4.3", NEED_INFO,
                          "Thiếu ngày bắt đầu hoặc loại hợp đồng")
    tenure = months_between(start.value, facts.as_of)
    problems = []
    if tenure < MIN_TENURE_MONTHS:
        problems.append(f"thâm niên {tenure} tháng < {MIN_TENURE_MONTHS} tháng")
    end = ex.get("labor_contract", "end_date")
    indefinite = "khong xac dinh" in norm(kind.value)
    if not indefinite:
        if not end:
            return RuleResult("R07", "Thâm niên và hợp đồng lao động", "4.3", NEED_INFO,
                              "Hợp đồng xác định thời hạn nhưng không đọc được ngày kết thúc", _ev(start, kind))
        remaining = months_between(facts.as_of, end.value)
        if remaining < MIN_FIXED_TERM_REMAINING:
            problems.append(f"hợp đồng chỉ còn {remaining} tháng hiệu lực")
    detail = f"Thâm niên {tenure} tháng; {kind.value}"
    if not indefinite and end:
        detail += f", hết hạn {fmt_date(end.value)}"
    if problems:
        return RuleResult("R07", "Thâm niên và hợp đồng lao động", "4.3", FAIL,
                          detail + " — " + "; ".join(problems), _ev(start, kind, end))
    return RuleResult("R07", "Thâm niên và hợp đồng lao động", "4.3", PASS, detail, _ev(start, kind, end))


def _r_amount(ex: Extraction, facts: Facts) -> RuleResult:
    ev = ex.get("loan_application", "requested_amount")
    if not ev or not facts.income:
        return RuleResult("R08", "Hạn mức số tiền vay", "5.1", NEED_INFO, "Thiếu số tiền vay hoặc thu nhập")
    cap = min(MAX_AMOUNT, INCOME_MULTIPLE * facts.income)
    ok = ev.value <= cap
    detail = (f"Đề nghị {fmt_vnd(ev.value)}; hạn mức tối đa {fmt_vnd(cap)} "
              f"(thấp hơn giữa {fmt_vnd(MAX_AMOUNT)} và {INCOME_MULTIPLE} × thu nhập)")
    return RuleResult("R08", "Hạn mức số tiền vay", "5.1", PASS if ok else FAIL, detail, _ev(ev))


def _r_term(ex: Extraction, facts: Facts) -> RuleResult:
    ev = ex.get("loan_application", "term_months")
    if not ev:
        return RuleResult("R09", "Thời hạn vay", "5.2", NEED_INFO, "Không đọc được thời hạn vay")
    ok = 6 <= ev.value <= 60
    return RuleResult("R09", "Thời hạn vay", "5.2", PASS if ok else FAIL,
                      f"{ev.value} tháng (cho phép 6–60 tháng)", _ev(ev))


def _r_dti(ex: Extraction, facts: Facts) -> RuleResult:
    if facts.dti is None:
        return RuleResult("R10", "Tỷ lệ nợ trên thu nhập (DTI)", "5.3", NEED_INFO,
                          "Thiếu dữ liệu để tính DTI")
    ok = facts.dti <= MAX_DTI
    detail = (f"DTI {facts.dti * 100:.1f}% = (trả góp ước tính {fmt_vnd(facts.installment)} "
              f"+ nợ hiện tại {fmt_vnd(facts.existing_debt)}) / thu nhập {fmt_vnd(facts.income)}; "
              f"giới hạn {MAX_DTI * 100:.0f}%. Trả góp tính theo niên kim, lãi suất tham chiếu "
              f"{REFERENCE_RATE * 100:.0f}%/năm (Điều 5.4)")
    return RuleResult("R10", "Tỷ lệ nợ trên thu nhập (DTI)", "5.3", PASS if ok else FAIL, detail,
                      _ev(ex.get("loan_application", "existing_monthly_debt"),
                          ex.get("loan_application", "requested_amount")))


RULES = [_r_documents, _r_age, _r_id_valid, _r_consistency, _r_income, _r_salary_history,
         _r_employment, _r_amount, _r_term, _r_dti]


def evaluate(ex: Extraction, as_of: date) -> tuple[Facts, list[RuleResult], str]:
    facts = compute_facts(ex, as_of)
    results = [rule(ex, facts) for rule in RULES]
    if any(r.status == FAIL for r in results):
        verdict = "REJECT"
    elif any(r.status == NEED_INFO for r in results):
        verdict = "NEED_INFO"
    else:
        verdict = "APPROVE"
    return facts, results, verdict
