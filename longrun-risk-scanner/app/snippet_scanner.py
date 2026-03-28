"""Scan a line range within a Java file."""

from __future__ import annotations

from pathlib import Path

from app.models import CandidateFinding, RiskRule
from app.risk_engine import build_scan_context, detect_candidates
from app.utils import read_text


def scan_snippet(
    path: Path,
    start_line: int,
    end_line: int,
    rules: dict[str, RiskRule],
) -> list[CandidateFinding]:
    text = read_text(path)
    lines = text.splitlines(keepends=True)
    ctx = build_scan_context(str(path.resolve()), lines)
    return detect_candidates(rules, ctx, line_start_filter=start_line, line_end_filter=end_line)
