"""SQLite persistence for scan sessions and findings."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.models import (
    Confidence,
    Finding,
    FindingStatus,
    ScanSession,
    Severity,
    VerifierSource,
    utc_now,
)


def _dt_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        return dt.replace(microsecond=0).isoformat() + "Z"
    return dt.astimezone().replace(microsecond=0).isoformat()


def _parse_dt(s: str) -> datetime:
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


class Storage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        with self._conn() as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS scan_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    root_path TEXT NOT NULL,
                    label TEXT DEFAULT '',
                    status TEXT DEFAULT 'complete',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS findings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scan_id INTEGER NOT NULL,
                    risk_id TEXT NOT NULL,
                    risk_name TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    line_start INTEGER NOT NULL,
                    line_end INTEGER NOT NULL,
                    snippet TEXT NOT NULL,
                    matched_signals TEXT,
                    initial_reason TEXT,
                    evidence TEXT,
                    status TEXT NOT NULL,
                    confidence TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    false_positive_note TEXT,
                    long_run_impact TEXT,
                    near_fix TEXT,
                    long_term_fix TEXT,
                    verifier_source TEXT NOT NULL,
                    context_summary TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (scan_id) REFERENCES scan_sessions(id)
                );
                CREATE INDEX IF NOT EXISTS idx_findings_scan ON findings(scan_id);
                CREATE INDEX IF NOT EXISTS idx_findings_status ON findings(status);
                CREATE INDEX IF NOT EXISTS idx_findings_risk ON findings(risk_id);
                """
            )

    def create_scan_session(self, root_path: str, label: str = "") -> int:
        now = _dt_iso(utc_now())
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO scan_sessions (root_path, label, status, created_at, updated_at) VALUES (?,?,?,?,?)",
                (root_path, label, "complete", now, now),
            )
            return int(cur.lastrowid)

    def get_scan_session(self, scan_id: int) -> Optional[ScanSession]:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM scan_sessions WHERE id = ?", (scan_id,)
            ).fetchone()
        if not row:
            return None
        return ScanSession(
            id=row["id"],
            root_path=row["root_path"],
            created_at=_parse_dt(row["created_at"]),
            updated_at=_parse_dt(row["updated_at"]),
            label=row["label"] or "",
            status=row["status"] or "complete",
        )

    def insert_finding(
        self,
        scan_id: int,
        risk_id: str,
        risk_name: str,
        file_path: str,
        line_start: int,
        line_end: int,
        snippet: str,
        matched_signals: list[str],
        initial_reason: str,
        evidence: dict[str, Any],
        status: FindingStatus = FindingStatus.NEW,
        confidence: Confidence = Confidence.LOW,
        severity: Severity = Severity.MEDIUM,
        false_positive_note: str = "",
        long_run_impact: str = "",
        near_fix: str = "",
        long_term_fix: str = "",
        verifier_source: VerifierSource = VerifierSource.LOCAL,
        context_summary: str = "",
    ) -> int:
        now = _dt_iso(utc_now())
        with self._conn() as c:
            cur = c.execute(
                """
                INSERT INTO findings (
                    scan_id, risk_id, risk_name, file_path, line_start, line_end, snippet,
                    matched_signals, initial_reason, evidence, status, confidence, severity,
                    false_positive_note, long_run_impact, near_fix, long_term_fix,
                    verifier_source, context_summary, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    scan_id,
                    risk_id,
                    risk_name,
                    file_path,
                    line_start,
                    line_end,
                    snippet,
                    json.dumps(matched_signals),
                    initial_reason,
                    json.dumps(evidence),
                    status.value,
                    confidence.value,
                    severity.value,
                    false_positive_note,
                    long_run_impact,
                    near_fix,
                    long_term_fix,
                    verifier_source.value,
                    context_summary,
                    now,
                    now,
                ),
            )
            return int(cur.lastrowid)

    def update_finding(
        self,
        finding_id: int,
        *,
        status: Optional[FindingStatus] = None,
        confidence: Optional[Confidence] = None,
        severity: Optional[Severity] = None,
        evidence: Optional[dict[str, Any]] = None,
        false_positive_note: Optional[str] = None,
        long_run_impact: Optional[str] = None,
        near_fix: Optional[str] = None,
        long_term_fix: Optional[str] = None,
        verifier_source: Optional[VerifierSource] = None,
        context_summary: Optional[str] = None,
        initial_reason: Optional[str] = None,
    ) -> None:
        fields: list[str] = []
        vals: list[Any] = []
        if status is not None:
            fields.append("status = ?")
            vals.append(status.value)
        if confidence is not None:
            fields.append("confidence = ?")
            vals.append(confidence.value)
        if severity is not None:
            fields.append("severity = ?")
            vals.append(severity.value)
        if evidence is not None:
            fields.append("evidence = ?")
            vals.append(json.dumps(evidence))
        if false_positive_note is not None:
            fields.append("false_positive_note = ?")
            vals.append(false_positive_note)
        if long_run_impact is not None:
            fields.append("long_run_impact = ?")
            vals.append(long_run_impact)
        if near_fix is not None:
            fields.append("near_fix = ?")
            vals.append(near_fix)
        if long_term_fix is not None:
            fields.append("long_term_fix = ?")
            vals.append(long_term_fix)
        if verifier_source is not None:
            fields.append("verifier_source = ?")
            vals.append(verifier_source.value)
        if context_summary is not None:
            fields.append("context_summary = ?")
            vals.append(context_summary)
        if initial_reason is not None:
            fields.append("initial_reason = ?")
            vals.append(initial_reason)
        if not fields:
            return
        fields.append("updated_at = ?")
        vals.append(_dt_iso(utc_now()))
        vals.append(finding_id)
        sql = "UPDATE findings SET " + ", ".join(fields) + " WHERE id = ?"
        with self._conn() as c:
            c.execute(sql, vals)

    def get_finding(self, finding_id: int) -> Optional[Finding]:
        with self._conn() as c:
            row = c.execute("SELECT * FROM findings WHERE id = ?", (finding_id,)).fetchone()
        if not row:
            return None
        return self._row_to_finding(row)

    def list_findings(
        self,
        *,
        scan_id: Optional[int] = None,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        min_confidence: Optional[str] = None,
    ) -> list[Finding]:
        q = "SELECT * FROM findings WHERE 1=1"
        args: list[Any] = []
        if scan_id is not None:
            q += " AND scan_id = ?"
            args.append(scan_id)
        if status:
            q += " AND status = ?"
            args.append(status)
        if severity:
            q += " AND severity = ?"
            args.append(severity)
        q += " ORDER BY id ASC"
        with self._conn() as c:
            rows = c.execute(q, args).fetchall()
        out = [self._row_to_finding(r) for r in rows]
        if min_confidence:
            order = {"low": 0, "medium": 1, "high": 2}
            thr = order.get(min_confidence, 0)
            out = [f for f in out if order.get(f.confidence.value, 0) >= thr]
        return out

    def list_scans(self, limit: int = 50) -> list[ScanSession]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM scan_sessions ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            ScanSession(
                id=r["id"],
                root_path=r["root_path"],
                created_at=_parse_dt(r["created_at"]),
                updated_at=_parse_dt(r["updated_at"]),
                label=r["label"] or "",
                status=r["status"] or "complete",
            )
            for r in rows
        ]

    def _row_to_finding(self, row: sqlite3.Row) -> Finding:
        return Finding(
            id=row["id"],
            scan_id=row["scan_id"],
            risk_id=row["risk_id"],
            risk_name=row["risk_name"],
            file_path=row["file_path"],
            line_start=row["line_start"],
            line_end=row["line_end"],
            snippet=row["snippet"] or "",
            matched_signals=json.loads(row["matched_signals"] or "[]"),
            initial_reason=row["initial_reason"] or "",
            evidence=json.loads(row["evidence"] or "{}"),
            status=FindingStatus(row["status"]),
            confidence=Confidence(row["confidence"]),
            severity=Severity(row["severity"]),
            false_positive_note=row["false_positive_note"] or "",
            long_run_impact=row["long_run_impact"] or "",
            near_fix=row["near_fix"] or "",
            long_term_fix=row["long_term_fix"] or "",
            verifier_source=VerifierSource(row["verifier_source"]),
            created_at=_parse_dt(row["created_at"]),
            updated_at=_parse_dt(row["updated_at"]),
            context_summary=row["context_summary"] or "",
        )
