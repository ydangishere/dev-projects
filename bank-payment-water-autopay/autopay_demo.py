#!/usr/bin/env python3
"""Water-bill AutoPay simulation. No connection to a real bank."""
import argparse
import copy
import json
import os
from datetime import date
from pathlib import Path

DEFAULT_STATE = {
    "balance_vnd": 1500000,
    "mandate": {
        "id": "mandate_demo_001",
        "active": True,
        "biller_id": "WATER_HCM_DEMO",
        "customer_code": "WATER-001234",
        "max_amount_vnd": 500000
    },
    "payments": {},
    "messages": []
}

def run_bill(state, period, amount_vnd):
    """Process one billing period, enforce mandate and prevent repeat debit."""
    if amount_vnd <= 0:
        raise ValueError("amount_vnd must be positive")
    mandate = state["mandate"]
    key = f'{mandate["biller_id"]}:{mandate["customer_code"]}:{period}'
    if key in state["payments"]:
        return {"status": "ALREADY_PAID", "key": key, "balance_vnd": state["balance_vnd"]}
    if not mandate.get("active"):
        status = "MANDATE_INACTIVE"
    elif amount_vnd > mandate["max_amount_vnd"]:
        status = "LIMIT_EXCEEDED"
    elif state["balance_vnd"] < amount_vnd:
        status = "INSUFFICIENT_FUNDS"
    else:
        status = "SUCCESS"
    if status == "SUCCESS":
        state["messages"].append({"type": "AUTOPAY_PRE_DEBIT", "period": period, "amount_vnd": amount_vnd})
        state["balance_vnd"] -= amount_vnd
        state["payments"][key] = {"status": "SUCCESS", "amount_vnd": amount_vnd, "period": period}
        state["messages"].append({"type": "AUTOPAY_SUCCESS", "period": period, "amount_vnd": amount_vnd, "balance_vnd": state["balance_vnd"]})
    else:
        state["messages"].append({"type": "AUTOPAY_BLOCKED", "period": period, "reason": status})
    return {"status": status, "key": key, "balance_vnd": state["balance_vnd"]}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--period", default=date.today().strftime("%Y-%m"), help="Billing period YYYY-MM")
    parser.add_argument("--amount", type=int, default=189000, help="Water bill amount in VND")
    parser.add_argument("--state", default="data/state.json", help="Demo state file")
    args = parser.parse_args()
    try:
        date.fromisoformat(args.period + "-01")
    except ValueError:
        parser.error("--period must be YYYY-MM")
    if args.amount <= 0:
        parser.error("--amount must be positive")
    path = Path(args.state)
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else copy.deepcopy(DEFAULT_STATE)
    result = run_bill(state, args.period, args.amount)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)
    print(json.dumps({"result": result, "last_message": state["messages"][-1] if state["messages"] else None}, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
