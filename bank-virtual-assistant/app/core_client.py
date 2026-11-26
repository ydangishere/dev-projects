"""How the assistant reaches the bank's service layer.

The assistant never talks to the core directly. It gets a `CoreClient` that exposes
only the operations it is allowed to use (reads, create a pending transfer, cancel it). Confirming a transfer is deliberately
NOT on this interface: only the customer, through the OTP form, can do that.

* InProcessCoreClient — calls the simulated core in the same process (default demo).
* HttpCoreClient — calls the same contract over REST (CORE_BASE_URL), the way a Python
  AI service would call the bank's Java/Spring Boot API layer.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Protocol

from .core_bank import CoreBankingService, CoreError


class CoreClient(Protocol):
    def get_balance(self, account_id: str) -> dict: ...
    def list_transactions(self, account_id: str, start: datetime | None = None, end: datetime | None = None,
                          category: str | None = None, limit: int | None = None) -> list[dict]: ...
    def list_beneficiaries(self, customer_id: str) -> list[dict]: ...
    def create_transfer(self, account_id: str, beneficiary_id: str, amount: int, note: str = "") -> dict: ...
    def cancel_transfer(self, transfer_id: str) -> dict: ...


class InProcessCoreClient:
    def __init__(self, service: CoreBankingService):
        self._service = service

    def get_balance(self, account_id: str) -> dict:
        return self._service.get_balance(account_id)

    def list_transactions(self, account_id, start=None, end=None, category=None, limit=None) -> list[dict]:
        return self._service.list_transactions(account_id, start, end, category, limit)

    def list_beneficiaries(self, customer_id: str) -> list[dict]:
        return self._service.list_beneficiaries(customer_id)

    def create_transfer(self, account_id: str, beneficiary_id: str, amount: int, note: str = "") -> dict:
        return self._service.create_transfer(account_id, beneficiary_id, amount, note)

    def cancel_transfer(self, transfer_id: str) -> dict:
        return self._service.cancel_transfer(transfer_id)


class HttpCoreClient:
    def __init__(self, base_url: str, timeout: float = 5.0, token: str = ""):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.token = token

    def _call(self, method: str, path: str, query: dict | None = None, body: dict | None = None):
        url = f"{self.base_url}{path}"
        if query:
            url += "?" + urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            try:
                detail = json.loads(exc.read().decode()).get("detail", {})
            except (ValueError, AttributeError):
                detail = {}
            raise CoreError(detail.get("code", f"HTTP_{exc.code}"), detail.get("message", "Lỗi dịch vụ lõi")) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise CoreError("CORE_UNAVAILABLE", "Hệ thống lõi tạm thời không phản hồi") from exc

    def get_balance(self, account_id: str) -> dict:
        return self._call("GET", f"/core/v1/accounts/{account_id}/balance")

    def list_transactions(self, account_id, start=None, end=None, category=None, limit=None) -> list[dict]:
        query = {"start": start.isoformat() if start else None, "end": end.isoformat() if end else None,
                 "category": category, "limit": limit}
        return self._call("GET", f"/core/v1/accounts/{account_id}/transactions", query)

    def list_beneficiaries(self, customer_id: str) -> list[dict]:
        return self._call("GET", f"/core/v1/customers/{customer_id}/beneficiaries")

    def create_transfer(self, account_id: str, beneficiary_id: str, amount: int, note: str = "") -> dict:
        return self._call("POST", "/core/v1/transfers", body={"account_id": account_id, "beneficiary_id": beneficiary_id,
                                                               "amount": amount, "note": note})

    def cancel_transfer(self, transfer_id: str) -> dict:
        return self._call("POST", f"/core/v1/transfers/{transfer_id}/cancel")
