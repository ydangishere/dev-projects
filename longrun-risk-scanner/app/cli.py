"""CLI argument parsing and command dispatch."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from app.config import load_config
from app.context_expander import context_pack_from_finding
from app.llm_verifier import verify_with_llm
from app.models import (
    Confidence,
    FindingStatus,
    Severity,
    VerifierSource,
)
from app.reporter import export_scan, terminal_summary
from app.rule_loader import load_rules
from app.scanner import run_snippet_scan
from app.storage import Storage
from app.utils import format_location, iter_java_files
from app.file_scanner import scan_java_file
from app.verifier import merge_verification, verify_locally


def _parse_severity(s: str) -> Severity:
    m = {"low": Severity.LOW, "medium": Severity.MEDIUM, "high": Severity.HIGH}
    return m.get(s.lower(), Severity.MEDIUM)


def _parse_confidence(s: str) -> Confidence:
    m = {"low": Confidence.LOW, "medium": Confidence.MEDIUM, "high": Confidence.HIGH}
    return m.get(s.lower(), Confidence.MEDIUM)


def _confidence_rank(c: Confidence) -> int:
    return {"low": 0, "medium": 1, "high": 2}[c.value]


def cmd_scan(args: argparse.Namespace) -> int:
    cfg = load_config()
    rules = load_rules(cfg.rules_path)
    storage = Storage(cfg.db_path)
    storage.init_schema()
    root = Path(args.path).resolve()
    scan_id = storage.create_scan_session(str(root), label=args.label or "")
    total = 0
    for jp in iter_java_files(root):
        for c in scan_java_file(jp, rules):
            r = rules[c.risk_id]
            storage.insert_finding(
                scan_id=scan_id,
                risk_id=c.risk_id,
                risk_name=r.name,
                file_path=str(jp.resolve()),
                line_start=c.line_start,
                line_end=c.line_end,
                snippet=c.snippet,
                matched_signals=c.matched_signals,
                initial_reason=c.initial_reason,
                evidence=c.evidence,
                status=FindingStatus.NEW,
                confidence=Confidence.LOW,
                severity=_parse_severity(r.default_severity),
                false_positive_note="; ".join(r.false_positive_notes[:1]) if r.false_positive_notes else "",
                long_run_impact=r.long_run_impact,
                near_fix=r.near_fix_templates[0] if r.near_fix_templates else "",
                long_term_fix=r.long_term_fix_templates[0] if r.long_term_fix_templates else "",
                verifier_source=VerifierSource.LOCAL,
                context_summary="",
            )
            total += 1
    jpath, mpath = export_scan(storage, cfg.scans_dir, scan_id)
    sess = storage.get_scan_session(scan_id)
    findings = storage.list_findings(scan_id=scan_id)
    print(f"Scan session {scan_id}: {total} candidate finding(s).")
    print(f"JSON: {jpath}")
    print(f"Markdown: {mpath}")
    if sess:
        print(terminal_summary(sess, findings))
    return 0


def cmd_scan_snippet(args: argparse.Namespace) -> int:
    cfg = load_config()
    rules = load_rules(cfg.rules_path)
    storage = Storage(cfg.db_path)
    storage.init_schema()
    fp = Path(args.file).resolve()
    root = fp.parent if args.root else fp.parent
    scan_id = storage.create_scan_session(str(root), label="snippet")
    cands = run_snippet_scan(fp, args.start_line, args.end_line, rules)
    for c in cands:
        r = rules[c.risk_id]
        storage.insert_finding(
            scan_id=scan_id,
            risk_id=c.risk_id,
            risk_name=r.name,
            file_path=str(fp),
            line_start=c.line_start,
            line_end=c.line_end,
            snippet=c.snippet,
            matched_signals=c.matched_signals,
            initial_reason=c.initial_reason,
            evidence=c.evidence,
            status=FindingStatus.VERIFYING,
            confidence=Confidence.LOW,
            severity=_parse_severity(r.default_severity),
            false_positive_note="; ".join(r.false_positive_notes[:1]) if r.false_positive_notes else "",
            long_run_impact=r.long_run_impact,
            near_fix=r.near_fix_templates[0] if r.near_fix_templates else "",
            long_term_fix=r.long_term_fix_templates[0] if r.long_term_fix_templates else "",
            verifier_source=VerifierSource.LOCAL,
            context_summary="Snippet scan — expand with verify for full context.",
        )
    jpath, mpath = export_scan(storage, cfg.scans_dir, scan_id)
    print(f"Snippet scan session {scan_id}: {len(cands)} finding(s).")
    print(f"JSON: {jpath}")
    print(f"Markdown: {mpath}")
    return 0


def _project_root_for_scan(storage: Storage, scan_id: int) -> Optional[Path]:
    s = storage.get_scan_session(scan_id)
    if not s:
        return None
    return Path(s.root_path)


def cmd_verify(args: argparse.Namespace) -> int:
    cfg = load_config()
    rules = load_rules(cfg.rules_path)
    storage = Storage(cfg.db_path)
    storage.init_schema()
    f = storage.get_finding(args.finding_id)
    if not f:
        print(f"Finding {args.finding_id} not found.", file=sys.stderr)
        return 1
    rule = rules.get(f.risk_id)
    if not rule:
        print(f"Rule {f.risk_id} missing from catalog.", file=sys.stderr)
        return 1
    proj = _project_root_for_scan(storage, f.scan_id)
    pack = context_pack_from_finding(f, rule, cfg, proj)
    local = verify_locally(f, pack, rule)
    llm_res = verify_with_llm(cfg, pack) if cfg.llm_enabled else None
    merged = merge_verification(local, llm_res)

    status = FindingStatus.VERIFYING
    if merged.confirmed is True:
        status = FindingStatus.CONFIRMED
    elif merged.confirmed is False:
        status = FindingStatus.DISMISSED

    vsrc = merged.verifier_source
    if llm_res is None:
        vsrc = VerifierSource.LOCAL

    ctx_summary = (
        f"class={pack.enclosing_class[:120]}; method={pack.enclosing_method[:120]}; "
        f"annotations={','.join(pack.annotations_in_scope[:8])}"
    )
    storage.update_finding(
        args.finding_id,
        status=status,
        confidence=merged.confidence,
        false_positive_note=merged.false_positive_possibility,
        long_run_impact=merged.why_risky_long_term,
        near_fix=merged.suggested_near_fix,
        long_term_fix=merged.suggested_long_term_fix,
        verifier_source=vsrc,
        context_summary=ctx_summary,
        evidence={**f.evidence, "verification": merged.raw},
    )
    loc = format_location(f.file_path, f.line_start, f.line_end)
    print(f"Finding {args.finding_id} -> {status.value} ({merged.confidence.value}) @ {loc}")
    print(f"Evidence: {merged.evidence_summary}")
    return 0


def cmd_verify_scan(args: argparse.Namespace) -> int:
    cfg = load_config()
    load_rules(cfg.rules_path)
    storage = Storage(cfg.db_path)
    storage.init_schema()
    if args.status:
        findings = storage.list_findings(
            scan_id=args.scan_id, status=args.status, severity=args.severity
        )
    else:
        findings = [
            f
            for f in storage.list_findings(scan_id=args.scan_id, severity=args.severity)
            if f.status in (FindingStatus.NEW, FindingStatus.VERIFYING)
        ]
    min_c = _parse_confidence(args.min_confidence) if args.min_confidence else Confidence.LOW
    thr = _confidence_rank(min_c)
    for f in findings:
        if _confidence_rank(f.confidence) < thr:
            continue
        ns = argparse.Namespace(finding_id=f.id)
        cmd_verify(ns)
    jpath, mpath = export_scan(storage, cfg.scans_dir, args.scan_id)
    print(f"Exports:\n  {jpath}\n  {mpath}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    cfg = load_config()
    storage = Storage(cfg.db_path)
    storage.init_schema()
    jpath, mpath = export_scan(storage, cfg.scans_dir, args.scan_id)
    sess = storage.get_scan_session(args.scan_id)
    findings = storage.list_findings(scan_id=args.scan_id)
    if sess:
        print(terminal_summary(sess, findings))
    print(f"JSON: {jpath}")
    print(f"Markdown: {mpath}")
    return 0


def cmd_list_findings(args: argparse.Namespace) -> int:
    cfg = load_config()
    storage = Storage(cfg.db_path)
    storage.init_schema()
    findings = storage.list_findings(
        scan_id=args.scan_id, status=args.status, severity=args.severity
    )
    for f in findings:
        loc = format_location(f.file_path, f.line_start, f.line_end)
        print(f"{f.id}\t{f.status.value}\t{f.risk_id}\t{loc}")
    return 0


def cmd_show_finding(args: argparse.Namespace) -> int:
    cfg = load_config()
    storage = Storage(cfg.db_path)
    storage.init_schema()
    f = storage.get_finding(args.finding_id)
    if not f:
        print("Not found.", file=sys.stderr)
        return 1
    loc = format_location(f.file_path, f.line_start, f.line_end)
    print(f"ID: {f.id}  scan: {f.scan_id}")
    print(f"{f.risk_id} {f.risk_name}")
    print(loc)
    print(f"status={f.status.value} confidence={f.confidence.value} severity={f.severity.value}")
    print(f"signals: {f.matched_signals}")
    print(f"reason: {f.initial_reason}")
    print(f"context: {f.context_summary}")
    print(f"false_positive: {f.false_positive_note}")
    print(f"near: {f.near_fix}")
    print(f"long: {f.long_term_fix}")
    print("--- snippet ---")
    print(f.snippet[:8000])
    return 0


def cmd_gui(args: argparse.Namespace) -> int:
    """Open Tkinter path picker + results (same as python app/scan_gui.py)."""
    from app.scan_gui import main as gui_main

    gui_main()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="longrun-risk-scanner",
        description="Local-first Java long-run risk scanner.",
        epilog="De mo cua so GUI (dan duong dan scan):  python app/main.py gui   hoac   python app/scan_gui.py",
    )
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("scan", help="Scan a file or directory tree")
    s.add_argument("--path", required=True, help="File or root folder")
    s.add_argument("--label", default="", help="Optional session label")

    ss = sub.add_parser("scan-snippet", help="Scan a line range in one file")
    ss.add_argument("--file", required=True)
    ss.add_argument("--start-line", type=int, required=True)
    ss.add_argument("--end-line", type=int, required=True)
    ss.add_argument("--root", action="store_true", help="Unused; reserved for project root hint")

    v = sub.add_parser("verify", help="Verify one finding")
    v.add_argument("--finding-id", type=int, required=True)

    vs = sub.add_parser("verify-scan", help="Verify findings in a scan")
    vs.add_argument("--scan-id", type=int, required=True)
    vs.add_argument("--status", default=None, help="Only findings with this status (default: new+verifying)")
    vs.add_argument("--severity", default=None, choices=["low", "medium", "high"])
    vs.add_argument("--min-confidence", default="low", choices=["low", "medium", "high"])

    r = sub.add_parser("report", help="Export JSON/Markdown for a scan")
    r.add_argument("--scan-id", type=int, required=True)

    lf = sub.add_parser("list-findings", help="List findings")
    lf.add_argument("--scan-id", type=int, default=None)
    lf.add_argument("--status", default=None)
    lf.add_argument("--severity", default=None, choices=["low", "medium", "high"])

    sh = sub.add_parser("show-finding", help="Show one finding")
    sh.add_argument("--finding-id", type=int, required=True)

    sub.add_parser("gui", help="Mo cua so: dan duong dan file/thu muc Java de scan (Tkinter)")

    return p


def main(argv: Optional[List[str]] = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)
    cmd = args.command
    if cmd == "scan":
        return cmd_scan(args)
    if cmd == "scan-snippet":
        return cmd_scan_snippet(args)
    if cmd == "verify":
        return cmd_verify(args)
    if cmd == "verify-scan":
        return cmd_verify_scan(args)
    if cmd == "report":
        return cmd_report(args)
    if cmd == "list-findings":
        return cmd_list_findings(args)
    if cmd == "show-finding":
        return cmd_show_finding(args)
    if cmd == "gui":
        return cmd_gui(args)
    parser.print_help()
    return 2
