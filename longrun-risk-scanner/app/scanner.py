"""High-level scan orchestration."""

from __future__ import annotations

from pathlib import Path

from app.models import CandidateFinding, RiskRule
from app.project_scanner import scan_project
from app.snippet_scanner import scan_snippet


def run_path_scan(path: Path, rules: dict[str, RiskRule]) -> list[tuple[str, list[CandidateFinding]]]:
    out: list[tuple[str, list[CandidateFinding]]] = []
    for p, cands in scan_project(path, rules):
        out.append((str(p.resolve()), cands))
    return out


def run_snippet_scan(
    path: Path,
    start: int,
    end: int,
    rules: dict[str, RiskRule],
) -> list[CandidateFinding]:
    return scan_snippet(path, start, end, rules)
