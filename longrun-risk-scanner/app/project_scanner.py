"""Traverse a project folder for Java files."""

from __future__ import annotations

from pathlib import Path

from app.models import CandidateFinding, RiskRule
from app.file_scanner import scan_java_file
from app.utils import iter_java_files


def scan_project(root: Path, rules: dict[str, RiskRule]) -> list[tuple[Path, list[CandidateFinding]]]:
    results: list[tuple[Path, list[CandidateFinding]]] = []
    for java in iter_java_files(root):
        cands = scan_java_file(java, rules)
        if cands:
            results.append((java, cands))
    return results
