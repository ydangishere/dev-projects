"""JSON and Markdown reports plus terminal-friendly summaries."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.models import Finding, ReportSummary, ScanSession
from app.storage import Storage
from app.utils import format_location


def severity_from_rule(default_severity: str) -> str:
    s = default_severity.lower()
    if s in ("low", "medium", "high"):
        return s
    return "medium"


def build_report_summary(session: ScanSession, findings: list[Finding]) -> ReportSummary:
    by_status: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for f in findings:
        by_status[f.status.value] = by_status.get(f.status.value, 0) + 1
        by_severity[f.severity.value] = by_severity.get(f.severity.value, 0) + 1
    preview = [
        {
            "id": f.id,
            "risk_id": f.risk_id,
            "location": format_location(f.file_path, f.line_start, f.line_end),
            "status": f.status.value,
        }
        for f in findings[:50]
    ]
    return ReportSummary(
        scan_id=session.id,
        root_path=session.root_path,
        created_at=session.created_at,
        total_findings=len(findings),
        by_status=by_status,
        by_severity=by_severity,
        findings_preview=preview,
    )


def write_json_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def findings_to_jsonable(findings: list[Finding]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for f in findings:
        out.append(
            {
                "id": f.id,
                "scan_id": f.scan_id,
                "risk_id": f.risk_id,
                "risk_name": f.risk_name,
                "file_path": f.file_path,
                "line_start": f.line_start,
                "line_end": f.line_end,
                "snippet": f.snippet,
                "matched_signals": f.matched_signals,
                "initial_reason": f.initial_reason,
                "evidence": f.evidence,
                "status": f.status.value,
                "confidence": f.confidence.value,
                "severity": f.severity.value,
                "false_positive_note": f.false_positive_note,
                "long_run_impact": f.long_run_impact,
                "near_fix": f.near_fix,
                "long_term_fix": f.long_term_fix,
                "verifier_source": f.verifier_source.value,
                "context_summary": f.context_summary,
                "created_at": f.created_at.isoformat(),
                "updated_at": f.updated_at.isoformat(),
            }
        )
    return out


def write_markdown_report(path: Path, session: ScanSession, findings: list[Finding]) -> None:
    lines: list[str] = []
    lines.append(f"# Long-run risk scan report")
    lines.append("")
    lines.append(f"- **Scan ID**: {session.id}")
    lines.append(f"- **Root**: `{session.root_path}`")
    lines.append(f"- **Created**: {session.created_at.isoformat()}")
    lines.append(f"- **Findings**: {len(findings)}")
    lines.append("")
    for f in findings:
        loc = format_location(f.file_path, f.line_start, f.line_end)
        lines.append(f"## Finding `{f.id}` — {f.risk_id} {f.risk_name}")
        lines.append("")
        lines.append(f"- **Location**: `{loc}`")
        lines.append(f"- **Status**: {f.status.value}")
        lines.append(f"- **Confidence**: {f.confidence.value}")
        lines.append(f"- **Severity**: {f.severity.value}")
        lines.append(f"- **Why flagged**: {f.initial_reason}")
        lines.append(f"- **Context summary**: {f.context_summary or '(none)'}")
        lines.append(f"- **Long-run impact**: {f.long_run_impact or '(see catalog)'}")
        lines.append(f"- **False-positive note**: {f.false_positive_note or '(none)'}")
        lines.append(f"- **Near fix**: {f.near_fix or '(none)'}")
        lines.append(f"- **Long-term fix**: {f.long_term_fix or '(none)'}")
        lines.append("")
        lines.append("```java")
        lines.append(f.snippet.rstrip()[:4000])
        lines.append("```")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def terminal_summary(session: ScanSession, findings: list[Finding]) -> str:
    lines: list[str] = []
    lines.append(f"Scan #{session.id} - {len(findings)} finding(s)")
    for f in findings:
        loc = format_location(f.file_path, f.line_start, f.line_end)
        lines.append(
            f"  [{f.id}] {f.risk_id} {f.status.value} {f.confidence.value} - {loc}"
        )
    return "\n".join(lines)


def export_scan(
    storage: Storage,
    scans_dir: Path,
    scan_id: int,
) -> tuple[Path, Path]:
    storage.init_schema()
    sess = storage.get_scan_session(scan_id)
    if not sess:
        raise ValueError(f"Unknown scan_id {scan_id}")
    findings = storage.list_findings(scan_id=scan_id)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary = build_report_summary(sess, findings)
    payload = {
        "scan": {
            "id": sess.id,
            "root_path": sess.root_path,
            "created_at": sess.created_at.isoformat(),
        },
        "summary": {
            "scan_id": summary.scan_id,
            "root_path": summary.root_path,
            "created_at": summary.created_at.isoformat(),
            "total_findings": summary.total_findings,
            "by_status": summary.by_status,
            "by_severity": summary.by_severity,
            "findings_preview": summary.findings_preview,
        },
        "findings": findings_to_jsonable(findings),
    }
    json_path = scans_dir / f"scan_{scan_id}_{ts}.json"
    md_path = scans_dir / f"scan_{scan_id}_{ts}.md"
    write_json_report(json_path, payload)
    write_markdown_report(md_path, sess, findings)
    return json_path, md_path
