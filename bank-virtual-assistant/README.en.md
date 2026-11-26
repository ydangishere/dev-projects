# Bank virtual assistant with OTP-gated transfers (demo)

[Tiếng Việt (main README)](./README.md)

A FastAPI chat demo for a Vietnamese banking app. Customers ask in Vietnamese (with or without accents, slang like "500k", "1tr5", "ck"); the assistant calls a **simulated core-banking API** for balance and history and **prepares** transfers that only execute when the customer enters an OTP.

> **Honest scope:** customers, accounts, transactions and contacts are **synthetic**. The "core" is an in-memory Python service standing in for the bank's API layer, not T24 or any real system. The OTP is shown in a fake SMS pop-up so the flow can be demoed in a browser. Default mode is **offline, no API key**. The LLM path is covered by tests with a mocked model only and **has not been run against a live API key**.

## Design

- **No direct core access:** the assistant gets a `CoreClient` exposing only reads, create-pending-transfer and cancel. There is **no confirm operation** on it; only the customer's OTP form can confirm. Setting `CORE_BASE_URL` switches the client to REST calls, the way a Python AI service would call a bank's Java service layer.
- **The LLM never writes numbers:** replies are fixed templates filled with API results. The optional LLM only classifies messages the rule parser cannot; an amount it returns is used only if that exact text is in the message and the rule parser reads the same value.
- **Guardrails first:** OTP bypass, prompt injection, other customers' data, unknown payees, OTP pasted into chat and investment advice are blocked before any LLM or core call, and logged as security events.
- **Core-enforced limits:** 50M VND per transfer, 100M per day, balance check, OTP expiry (3 min), lock after 3 wrong OTPs, idempotent confirmation.

## Run

```bash
cd bank-virtual-assistant
pip install -r requirements.txt
uvicorn app.main:app --reload       # http://127.0.0.1:8000  and /docs
pip install -r requirements-dev.txt && python -m pytest -q && python scripts/evaluate.py
```

## Offline evaluation

Intent 25/25, slots 28/28, attacks blocked 12/12, benign messages wrongly blocked 0/25, multi-turn flows 3/3. The cases were written alongside the rules, so this is a regression check, not accuracy on real customer chat. Keyword guardrails can be evaded by rephrasing; the real protection is that the assistant has no permission to confirm transfers or pay unknown accounts.
