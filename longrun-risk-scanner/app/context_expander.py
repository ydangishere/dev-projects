"""Expand snippet-level candidates to file and limited project context."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from app.config import AppConfig
from app.models import ContextPack, Finding, RiskRule
from app.utils import extract_annotations, read_text


_CLASS_RE = re.compile(
    r"^\s*(public|protected|private)?\s*(static\s+)?(final\s+)?(class|interface|enum|record)\s+(\w+)",
    re.MULTILINE,
)
_METHOD_RE = re.compile(
    r"^\s*(public|protected|private)\s+[\w<>,\s\[\]]+\s+(\w+)\s*\([^)]*\)\s*(throws\s+[\w.,\s]+)?\s*\{",
)


def _lines_of_file(path: Path) -> list[str]:
    t = read_text(path)
    return t.splitlines(keepends=True)


def find_enclosing_class(lines: list[str], line_1based: int) -> tuple[str, str]:
    """Return (class_name or '', class_signature_line or '')."""
    best = ("", "")
    for i, ln in enumerate(lines, start=1):
        if i > line_1based:
            break
        m = _CLASS_RE.match(ln.strip())
        if m:
            best = (m.group(5), ln.strip()[:200])
    return best


def find_enclosing_method(lines: list[str], line_1based: int) -> tuple[str, str]:
    """Return (method_name or '', first_line or '')."""
    best = ("", "")
    for i, ln in enumerate(lines, start=1):
        if i > line_1based:
            break
        m = _METHOD_RE.match(ln)
        if m and not ln.strip().startswith("if") and not ln.strip().startswith("for"):
            best = (m.group(2), ln.strip()[:220])
    return best


def collect_timeout_retry_clues(lines: list[str]) -> list[str]:
    clues: list[str] = []
    blob = "".join(lines[:400])
    patterns = [
        (r"setReadTimeout|setConnectTimeout|readTimeout|connectTimeout", "timeout_config"),
        (r"@Retryable|Retry|maxAttempts|backoff|ExponentialBackoff", "retry_config"),
        (r"@Transactional", "transactional"),
        (r"@Async|@Scheduled", "async_scheduled"),
    ]
    for rx, label in patterns:
        if re.search(rx, blob, re.I):
            clues.append(label)
    return clues


def infer_project_references(
    project_root: Path,
    symbol: str,
    max_refs: int,
    exclude: Path,
) -> list[str]:
    """Very light symbol grep — best-effort, may be empty."""
    if not symbol or len(symbol) < 3:
        return []
    refs: list[str] = []
    try:
        for p in project_root.rglob("*.java"):
            if p.resolve() == exclude.resolve():
                continue
            try:
                txt = read_text(p)
            except OSError:
                continue
            if symbol not in txt:
                continue
            refs.append(str(p.relative_to(project_root)))
            if len(refs) >= max_refs:
                break
    except OSError:
        pass
    return refs


def build_context_pack(
    rule: RiskRule,
    file_path: str,
    line_start: int,
    line_end: int,
    snippet: str,
    config: AppConfig,
    project_root: Optional[Path] = None,
) -> ContextPack:
    path = Path(file_path)
    lines = _lines_of_file(path)
    cls_name, cls_sig = find_enclosing_class(lines, line_start)
    meth_name, meth_sig = find_enclosing_method(lines, line_start)
    ann = extract_annotations(lines, max_scan=min(120, len(lines)))

    clues = collect_timeout_retry_clues(lines)
    inference_notes: list[str] = []
    inference_notes.append("Class/method boundaries are heuristic (brace/signature scan).")

    mid = (line_start + line_end) // 2
    pad = min(config.llm_max_context_lines // 2, 60)
    ns = max(1, mid - pad)
    ne = min(len(lines), mid + pad)
    nearby = "".join(lines[ns - 1 : ne])

    refs: list[str] = []
    if project_root and project_root.is_dir() and meth_name:
        refs = infer_project_references(project_root, meth_name, config.llm_max_project_references, path)

    excerpt = f"{rule.name}: {rule.description[:300]}"

    inferred_clues: list[str] = []
    inferred_clues.extend([f"file_clue:{c}" for c in clues])
    if refs:
        inferred_clues.append(f"symbol_refs_found:{len(refs)}")

    return ContextPack(
        risk_rule=rule,
        file_path=str(path),
        line_start=line_start,
        line_end=line_end,
        snippet=snippet,
        enclosing_class=f"{cls_name} | {cls_sig}" if cls_name else "(inferred unknown)",
        enclosing_method=f"{meth_name} | {meth_sig}" if meth_name else "(inferred unknown)",
        nearby_lines=nearby,
        annotations_in_scope=ann,
        inferred_clues=inferred_clues,
        inference_notes=inference_notes,
        project_references=refs,
        rule_text_excerpt=excerpt,
    )


def context_pack_from_finding(
    finding: Finding,
    rule: RiskRule,
    config: AppConfig,
    project_root: Optional[Path],
) -> ContextPack:
    return build_context_pack(
        rule,
        finding.file_path,
        finding.line_start,
        finding.line_end,
        finding.snippet,
        config,
        project_root,
    )
