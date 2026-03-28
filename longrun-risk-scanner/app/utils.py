"""Shared helpers: paths, Java-ish text, line regions."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Optional


DEFAULT_IGNORE_DIRS = frozenset(
    {
        ".git",
        "target",
        "build",
        "node_modules",
        ".idea",
        ".gradle",
        "out",
        "__pycache__",
        ".venv",
        "venv",
    }
)


def is_ignored_dir(name: str) -> bool:
    return name in DEFAULT_IGNORE_DIRS


def iter_java_files(root: Path) -> Iterable[Path]:
    root = root.resolve()
    if root.is_file() and root.suffix.lower() == ".java":
        yield root
        return
    for p in root.rglob("*.java"):
        try:
            rel = p.relative_to(root)
        except ValueError:
            continue
        if any(part in DEFAULT_IGNORE_DIRS for part in rel.parts):
            continue
        yield p


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def lines_to_snippet(lines: list[str], start: int, end: int) -> str:
    """1-based inclusive line numbers."""
    if start < 1:
        start = 1
    if end < start:
        end = start
    chunk = lines[start - 1 : end]
    return "".join(chunk)


def strip_java_comments_preserving_newlines(text: str) -> str:
    """Remove // and /* */ comments, keep newlines for line alignment."""
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        if i + 1 < n and text[i : i + 2] == "//":
            while i < n and text[i] != "\n":
                i += 1
            if i < n and text[i] == "\n":
                out.append("\n")
                i += 1
            continue
        if i + 1 < n and text[i : i + 2] == "/*":
            i += 2
            while i + 1 < n and text[i : i + 2] != "*/":
                if text[i] == "\n":
                    out.append("\n")
                i += 1
            i = min(i + 2, n)
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


def line_comment_stripped(line: str) -> str:
    """Remove trailing // comment from a single line."""
    in_string = False
    escape = False
    quote: Optional[str] = None
    for idx, ch in enumerate(line):
        if not in_string:
            if ch in ('"', "'"):
                in_string = True
                quote = ch
                escape = False
            elif ch == "/" and idx + 1 < len(line) and line[idx + 1] == "/":
                return line[:idx].rstrip()
        else:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                in_string = False
                quote = None
    return line.rstrip()


_ANNOTATION_PATTERN = re.compile(r"^\s*@(\w+)\s*(\(|$)")


def extract_annotations(lines: list[str], max_scan: int = 80) -> list[str]:
    found: list[str] = []
    for line in lines[:max_scan]:
        m = _ANNOTATION_PATTERN.match(line)
        if m:
            found.append(m.group(1))
    return found


def format_location(file_path: str, line_start: int, line_end: int) -> str:
    """Terminal-friendly clickable path."""
    fp = str(Path(file_path).as_posix())
    if line_start == line_end:
        return f"{fp}:{line_start}"
    return f"{fp}:{line_start}-{line_end}"


def clamp_line_range(
    line: int,
    context_before: int,
    context_after: int,
    total_lines: int,
) -> tuple[int, int]:
    start = max(1, line - context_before)
    end = min(total_lines, line + context_after)
    return start, end
