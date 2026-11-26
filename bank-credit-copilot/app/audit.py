"""Append-only JSONL audit trail. Identifiers are masked (policy Điều 7.1)."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

_LOCK = threading.Lock()


class AuditLog:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event: str, payload: dict) -> str:
        record = {"audit_id": uuid.uuid4().hex[:12],
                  "at": datetime.now(UTC).isoformat(timespec="seconds"),
                  "event": event, **payload}
        with _LOCK, self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record["audit_id"]

    def tail(self, limit: int = 20) -> list[dict]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()[-limit:]
        return [json.loads(line) for line in reversed(lines) if line.strip()]
