"""
Heuristic risk detection for Java sources.
Candidates are not definitive bugs — conservative signals + evidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

from app.models import CandidateFinding, RiskRule
from app.utils import line_comment_stripped, strip_java_comments_preserving_newlines


@dataclass
class ScanContext:
    file_path: str
    lines: list[str]
    stripped_lines: list[str]  # line comments stripped for matching
    full_text: str


def build_scan_context(file_path: str, lines: list[str]) -> ScanContext:
    text = "".join(lines)
    stripped = strip_java_comments_preserving_newlines(text)
    stripped_lines = stripped.splitlines(keepends=True)
    sl = [line_comment_stripped(x.rstrip("\n\r")) for x in lines]
    return ScanContext(
        file_path=file_path,
        lines=lines,
        stripped_lines=sl,
        full_text=text,
    )


def detect_candidates(
    rules: dict[str, RiskRule],
    ctx: ScanContext,
    line_start_filter: Optional[int] = None,
    line_end_filter: Optional[int] = None,
) -> list[CandidateFinding]:
    """If line_start_filter/end set, only emit findings overlapping that 1-based range."""
    all_findings: list[CandidateFinding] = []
    detectors = [
        _detect_risk_01,
        _detect_risk_02,
        _detect_risk_03,
        _detect_risk_04,
        _detect_risk_05,
        _detect_risk_06,
        _detect_risk_07,
        _detect_risk_08,
        _detect_risk_09,
        _detect_risk_10,
        _detect_risk_11,
        _detect_risk_12,
        _detect_risk_13,
        _detect_risk_14,
        _detect_risk_15,
        _detect_risk_16,
        _detect_risk_17,
        _detect_risk_18,
        _detect_risk_19,
        _detect_risk_20,
    ]
    for fn in detectors:
        all_findings.extend(fn(rules, ctx))

    if line_start_filter is None or line_end_filter is None:
        return all_findings

    def overlaps(f: CandidateFinding) -> bool:
        return not (f.line_end < line_start_filter or f.line_start > line_end_filter)

    return [f for f in all_findings if overlaps(f)]


def _snippet(ctx: ScanContext, start: int, end: int) -> str:
    return "".join(ctx.lines[start - 1 : end])


# --- RISK_01 ---
_NULL_SAFE = re.compile(r"\b(Optional\.ofNullable|Objects\.requireNonNull|@NonNull)\b")


def _detect_risk_01(rules: dict[str, RiskRule], ctx: ScanContext) -> list[CandidateFinding]:
    rid = "RISK_01"
    if rid not in rules:
        return []
    out: list[CandidateFinding] = []
    chain = re.compile(r"\)\s*\.\s*\w+\s*\(")
    for i, raw in enumerate(ctx.stripped_lines, start=1):
        line = raw.strip()
        if not line or line.startswith("import ") or line.startswith("package "):
            continue
        if _NULL_SAFE.search(line):
            continue
        if chain.search(line) and "null" not in line.lower():
            if re.search(r"\)\s*\.\s*(get|orElse|orElseGet|map|flatMap)\s*\(", line):
                continue
            out.append(
                CandidateFinding(
                    risk_id=rid,
                    line_start=i,
                    line_end=i,
                    snippet=_snippet(ctx, i, i),
                    matched_signals=["chained_calls_without_null_check"],
                    initial_reason="Chained calls on expression without obvious null-safety in this line.",
                    evidence={"line": line[:400]},
                )
            )
    return out[:30]


# --- RISK_02 ---
_CATCH_BROAD = re.compile(r"catch\s*\(\s*(Exception|Throwable)\s+\w+\s*\)")


def _detect_risk_02(rules: dict[str, RiskRule], ctx: ScanContext) -> list[CandidateFinding]:
    rid = "RISK_02"
    if rid not in rules:
        return []
    out: list[CandidateFinding] = []
    for i, raw in enumerate(ctx.stripped_lines, start=1):
        m = _CATCH_BROAD.search(raw)
        if not m:
            continue
        sig = "catch_exception" if "Exception" in m.group(1) else "catch_throwable"
        out.append(
            CandidateFinding(
                risk_id=rid,
                line_start=i,
                line_end=i,
                snippet=_snippet(ctx, i, i),
                matched_signals=[sig],
                initial_reason=f"Overly broad catch ({m.group(1)}).",
                evidence={"match": m.group(0)},
            )
        )
    return out


# --- RISK_03 ---
def _catch_block_lines(ctx: ScanContext, catch_line_idx: int) -> tuple[int, int, str]:
    """Approximate: from catch line to closing brace of block."""
    start = catch_line_idx
    depth = 0
    buf: list[str] = []
    for j in range(catch_line_idx - 1, len(ctx.lines)):
        line = ctx.lines[j]
        buf.append(line)
        depth += line.count("{") - line.count("}")
        if j >= catch_line_idx - 1 and depth <= 0 and "{" in ctx.lines[catch_line_idx - 1]:
            if j > catch_line_idx - 1:
                break
        if j >= catch_line_idx and depth == 0 and "}" in line:
            break
    end = min(len(ctx.lines), catch_line_idx + 25)
    block = "".join(ctx.lines[catch_line_idx - 1 : end])
    return catch_line_idx, min(len(ctx.lines), catch_line_idx + 8), block[:2000]


def _detect_risk_03(rules: dict[str, RiskRule], ctx: ScanContext) -> list[CandidateFinding]:
    rid = "RISK_03"
    if rid not in rules:
        return []
    out: list[CandidateFinding] = []
    for i, raw in enumerate(ctx.stripped_lines, start=1):
        if not re.search(r"^\s*catch\s*\(", raw):
            continue
        _, end_ln, block = _catch_block_lines(ctx, i)
        block_lower = block.lower()
        body = block[block.find("{") + 1 : block.rfind("}")] if "{" in block and "}" in block else block
        body_stripped = re.sub(r"\s+", " ", body).strip()
        signals: list[str] = []

        if re.search(r"catch\s*\([^)]+\)\s*\{\s*\}", block, re.DOTALL):
            signals.append("empty_catch")
        if "printstacktrace()" in block_lower and len(body_stripped) < 120:
            signals.append("only_printStackTrace")
        if signals:
            pass
        elif re.search(r"\blog\.(trace|debug|info|warn|error)\s*\(", block_lower):
            if not re.search(r"(throw|throw new)", block) and "return" not in body_stripped.lower():
                signals.append("only_logging_in_catch")
        if re.search(r"catch\s*\([^)]+\)\s*\{[^}]*return\s+(true|false|0|null|Optional\.empty)", block, re.DOTALL):
            signals.append("return_default_after_catch")

        if not signals:
            continue
        out.append(
            CandidateFinding(
                risk_id=rid,
                line_start=i,
                line_end=min(end_ln, i + 5),
                snippet=_snippet(ctx, i, min(end_ln, i + 5)),
                matched_signals=signals,
                initial_reason="Catch block may swallow errors or mask failure (heuristic).",
                evidence={"signals": signals, "block_excerpt": body_stripped[:500]},
            )
        )
    return out


# --- RISK_04 ---
def _detect_risk_04(rules: dict[str, RiskRule], ctx: ScanContext) -> list[CandidateFinding]:
    rid = "RISK_04"
    if rid not in rules:
        return []
    out: list[CandidateFinding] = []
    pat_while = re.compile(r"\bwhile\s*\(\s*true\s*\)")
    pat_for = re.compile(r"\bfor\s*\(\s*;\s*;\s*\)")
    for i, raw in enumerate(ctx.stripped_lines, start=1):
        if pat_while.search(raw) or pat_for.search(raw):
            out.append(
                CandidateFinding(
                    risk_id=rid,
                    line_start=i,
                    line_end=i,
                    snippet=_snippet(ctx, i, i),
                    matched_signals=["while_true" if pat_while.search(raw) else "for_infinite"],
                    initial_reason="Unbounded loop construct detected.",
                    evidence={"line": raw.strip()[:400]},
                )
            )
    return out


# --- RISK_05 ---
def _detect_risk_05(rules: dict[str, RiskRule], ctx: ScanContext) -> list[CandidateFinding]:
    rid = "RISK_05"
    if rid not in rules:
        return []
    out: list[CandidateFinding] = []
    retry_loop = re.compile(r"\bwhile\s*\([^)]*\)\s*\{[^}]*\bretry\b", re.DOTALL)
    no_max = re.compile(r"\b(retry|attempt)\b", re.I)
    has_max = re.compile(r"max(Attempts|Retries|Count)|MAX_\w+|attempt\s*<\s*\w+", re.I)
    text = "".join(ctx.lines)
    if retry_loop.search(text):
        block = retry_loop.search(text)
        if block and not has_max.search(block.group(0)):
            line_no = text[: block.start()].count("\n") + 1
            out.append(
                CandidateFinding(
                    risk_id=rid,
                    line_start=line_no,
                    line_end=line_no + 2,
                    snippet=_snippet(ctx, line_no, min(len(ctx.lines), line_no + 2)),
                    matched_signals=["retry_loop_no_max"],
                    initial_reason="Retry loop without obvious max attempts cap.",
                    evidence={},
                )
            )
    for i, raw in enumerate(ctx.stripped_lines, start=1):
        if "@Retryable" in raw and not re.search(r"maxAttempts\s*=", raw):
            out.append(
                CandidateFinding(
                    risk_id=rid,
                    line_start=i,
                    line_end=i,
                    snippet=_snippet(ctx, i, i),
                    matched_signals=["retryable_without_max"],
                    initial_reason="@Retryable without explicit maxAttempts on same line (check defaults).",
                    evidence={"line": raw.strip()[:400]},
                )
            )
        if no_max.search(raw) and "for" in raw and not has_max.search(raw):
            if "sleep" in raw.lower():
                out.append(
                    CandidateFinding(
                        risk_id=rid,
                        line_start=i,
                        line_end=i,
                        snippet=_snippet(ctx, i, i),
                        matched_signals=["constant_delay_retry"],
                        initial_reason="Possible tight retry loop; verify backoff and max attempts.",
                        evidence={"line": raw.strip()[:400]},
                    )
                )
    return out


# --- RISK_06 ---
_EXT_PATTERNS = [
    (
        re.compile(r"\brestTemplate\.\w+\s*\(", re.I),
        "rest_template_call",
    ),
    (re.compile(r"\bwebClient\.\w+", re.I), "webclient_call"),
    (re.compile(r"\bhttpURLConnection\b", re.I), "http_url_connection"),
    (re.compile(r"\bjdbcTemplate\.(query|update|execute|call)\b", re.I), "jdbc_template"),
    (re.compile(r"\bentityManager\.(persist|merge|createQuery)\b", re.I), "jpa_call"),
]


def _method_slice_lines(ctx: ScanContext, line: int) -> tuple[int, int]:
    """Rough method boundaries by brace scan upward and downward."""
    start = 1
    depth = 0
    for i in range(line - 1, -1, -1):
        if i < 0:
            break
        ln = ctx.stripped_lines[i]
        if re.search(r"\b(void|int|long|boolean|String|List|Optional|ResponseEntity|Mono|Flux)\b", ln) and "(" in ln:
            start = i + 1
            break
    end = len(ctx.lines)
    depth = 0
    seen_open = False
    for j in range(start - 1, len(ctx.lines)):
        ln = ctx.lines[j]
        if "{" in ln:
            seen_open = True
        if seen_open:
            depth += ln.count("{") - ln.count("}")
            if depth <= 0 and j + 1 > line:
                end = j + 1
                break
    return start, end


def _detect_risk_06(rules: dict[str, RiskRule], ctx: ScanContext) -> list[CandidateFinding]:
    rid = "RISK_06"
    if rid not in rules:
        return []
    out: list[CandidateFinding] = []
    timeout_hints = re.compile(
        r"(setReadTimeout|setConnectTimeout|readTimeout|connectTimeout|queryTimeout|"
        r"Duration\.of|@Timeout|Resilience4j|TimeLimiter|socketTimeout|Statement\.setQueryTimeout)",
        re.I,
    )
    for i, raw in enumerate(ctx.stripped_lines, start=1):
        for rx, label in _EXT_PATTERNS:
            if rx.search(raw):
                ms, me = _method_slice_lines(ctx, i)
                method_text = "".join(ctx.lines[ms - 1 : me])
                if timeout_hints.search(method_text):
                    continue
                out.append(
                    CandidateFinding(
                        risk_id=rid,
                        line_start=i,
                        line_end=i,
                        snippet=_snippet(ctx, i, i),
                        matched_signals=["blocking_call_no_timeout"],
                        initial_reason=f"External/blocked call ({label}) without obvious timeout in enclosing method.",
                        evidence={"pattern": label, "method_line_range": [ms, me]},
                    )
                )
                break
    return out


# --- RISK_07 ---
def _detect_risk_07(rules: dict[str, RiskRule], ctx: ScanContext) -> list[CandidateFinding]:
    rid = "RISK_07"
    if rid not in rules:
        return []
    out: list[CandidateFinding] = []
    pat = re.compile(r"Thread\.sleep\s*\(")
    for i, raw in enumerate(ctx.stripped_lines, start=1):
        if pat.search(raw):
            if re.search(r"@Test|test\s*\(", raw, re.I):
                continue
            out.append(
                CandidateFinding(
                    risk_id=rid,
                    line_start=i,
                    line_end=i,
                    snippet=_snippet(ctx, i, i),
                    matched_signals=["thread_sleep_in_service"],
                    initial_reason="Thread.sleep used — may block threads and create flaky timing.",
                    evidence={"line": raw.strip()[:400]},
                )
            )
    return out


# --- RISK_08 ---
def _detect_risk_08(rules: dict[str, RiskRule], ctx: ScanContext) -> list[CandidateFinding]:
    rid = "RISK_08"
    if rid not in rules:
        return []
    out: list[CandidateFinding] = []
    cf_start = re.compile(r"\b(CompletableFuture\.(runAsync|supplyAsync)|\w+\.thenApplyAsync)\s*\(")
    handled = re.compile(r"\.(get|join|whenComplete|exceptionally|handle)\s*\(")
    for i, raw in enumerate(ctx.stripped_lines, start=1):
        if not cf_start.search(raw):
            continue
        window = "".join(ctx.stripped_lines[i - 1 : min(len(ctx.lines), i + 12)])
        if handled.search(window):
            continue
        out.append(
            CandidateFinding(
                risk_id=rid,
                line_start=i,
                line_end=min(len(ctx.lines), i + 1),
                snippet=_snippet(ctx, i, min(len(ctx.lines), i + 3)),
                matched_signals=["completable_future_orphan"],
                initial_reason="Async pipeline may not handle completion or errors (heuristic over next lines).",
                evidence={"window_excerpt": window[:800]},
            )
        )
    exec_line = re.compile(r"\bexecutor\.execute\s*\(")
    for i, raw in enumerate(ctx.stripped_lines, start=1):
        if exec_line.search(raw) and "Runnable" in "".join(ctx.stripped_lines[max(0, i - 5) : i + 3]):
            out.append(
                CandidateFinding(
                    risk_id=rid,
                    line_start=i,
                    line_end=i,
                    snippet=_snippet(ctx, i, i),
                    matched_signals=["executor_execute_no_tracking"],
                    initial_reason="Executor.execute with no obvious error tracking nearby.",
                    evidence={"line": raw.strip()[:400]},
                )
            )
    return out


# --- RISK_09 ---
_STATIC_MUTABLE = re.compile(
    r"\bprivate\s+static\s+(final\s+)?(HashMap|HashSet|ArrayList|LinkedList|Map|List|Set|Collection)\s*<\s*[^>]+>\s+\w+\s*=",
    re.I,
)


def _detect_risk_09(rules: dict[str, RiskRule], ctx: ScanContext) -> list[CandidateFinding]:
    rid = "RISK_09"
    if rid not in rules:
        return []
    out: list[CandidateFinding] = []
    for i, raw in enumerate(ctx.stripped_lines, start=1):
        if _STATIC_MUTABLE.search(raw) and "unmodifiable" not in raw.lower():
            out.append(
                CandidateFinding(
                    risk_id=rid,
                    line_start=i,
                    line_end=i,
                    snippet=_snippet(ctx, i, i),
                    matched_signals=["static_mutable_collection"],
                    initial_reason="Static field with mutable collection type — possible shared mutable state.",
                    evidence={"line": raw.strip()[:400]},
                )
            )
    return out


# --- RISK_10 ---
_CONCURRENT_HINT = re.compile(r"@(?:Service|Component|RestController|Scheduled|Async)\b")


def _detect_risk_10(rules: dict[str, RiskRule], ctx: ScanContext) -> list[CandidateFinding]:
    rid = "RISK_10"
    if rid not in rules:
        return []
    text_head = "".join(ctx.lines[:120])
    if not _CONCURRENT_HINT.search(text_head):
        return []
    out: list[CandidateFinding] = []
    unsafe = re.compile(r"\b(new\s+HashMap\s*\(|new\s+ArrayList\s*\()", re.I)
    for i, raw in enumerate(ctx.stripped_lines, start=1):
        if unsafe.search(raw) and "Collections.synchronized" not in raw:
            out.append(
                CandidateFinding(
                    risk_id=rid,
                    line_start=i,
                    line_end=i,
                    snippet=_snippet(ctx, i, i),
                    matched_signals=["hashmap_in_async_class"],
                    initial_reason="Non-thread-safe collection in Spring-style component (heuristic).",
                    evidence={"line": raw.strip()[:400]},
                )
            )
    return out[:25]


# --- RISK_11 ---
def _detect_risk_11(rules: dict[str, RiskRule], ctx: ScanContext) -> list[CandidateFinding]:
    rid = "RISK_11"
    if rid not in rules:
        return []
    out: list[CandidateFinding] = []
    foreach = re.compile(r"for\s*\(\s*[^:]+\s*:\s*(\w+)\s*\)")
    mut = re.compile(r"\.(remove|add)\s*\(")
    for i, raw in enumerate(ctx.stripped_lines, start=1):
        m = foreach.search(raw)
        if not m:
            continue
        coll = m.group(1)
        window = "".join(ctx.stripped_lines[i : min(len(ctx.lines), i + 15)])
        if mut.search(window) and coll in window:
            out.append(
                CandidateFinding(
                    risk_id=rid,
                    line_start=i,
                    line_end=i,
                    snippet=_snippet(ctx, i, min(len(ctx.lines), i + 5)),
                    matched_signals=["remove_in_foreach"],
                    initial_reason="Possible structural modification while iterating enhanced-for collection.",
                    evidence={"collection": coll},
                )
            )
    return out


# --- RISK_12 ---
def _detect_risk_12(rules: dict[str, RiskRule], ctx: ScanContext) -> list[CandidateFinding]:
    rid = "RISK_12"
    if rid not in rules:
        return []
    out: list[CandidateFinding] = []
    new_stream = re.compile(r"\bnew\s+(FileInputStream|FileOutputStream|FileReader|FileWriter)\s*\(")
    for i, raw in enumerate(ctx.stripped_lines, start=1):
        if not new_stream.search(raw):
            continue
        window = "".join(ctx.stripped_lines[max(0, i - 3) : i + 2])
        if "try (" in window or "try(" in window.replace(" ", ""):
            continue
        out.append(
            CandidateFinding(
                risk_id=rid,
                line_start=i,
                line_end=i,
                snippet=_snippet(ctx, i, i),
                matched_signals=["stream_not_try_with_resources"],
                initial_reason="Resource created without try-with-resources (heuristic).",
                evidence={"line": raw.strip()[:400]},
            )
        )
    return out


# --- RISK_13 ---
def _detect_risk_13(rules: dict[str, RiskRule], ctx: ScanContext) -> list[CandidateFinding]:
    rid = "RISK_13"
    if rid not in rules:
        return []
    out: list[CandidateFinding] = []
    saves = len(re.findall(r"\.save\s*\(", "".join(ctx.stripped_lines)))
    has_tx = bool(re.search(r"@Transactional", "".join(ctx.lines[:200])))
    if saves >= 2 and not has_tx:
        line_no = next((i for i, l in enumerate(ctx.stripped_lines, 1) if ".save(" in l), 1)
        out.append(
            CandidateFinding(
                risk_id=rid,
                line_start=line_no,
                line_end=line_no,
                snippet=_snippet(ctx, line_no, line_no),
                matched_signals=["multi_save_no_transaction"],
                initial_reason="Multiple .save() calls with no @Transactional in file header region (weak heuristic).",
                evidence={"save_count": saves},
            )
        )
    return out


# --- RISK_14 ---
def _detect_risk_14(rules: dict[str, RiskRule], ctx: ScanContext) -> list[CandidateFinding]:
    rid = "RISK_14"
    if rid not in rules:
        return []
    out: list[CandidateFinding] = []
    text = "".join(ctx.lines)
    if re.search(r"@Retryable", text) and not re.search(r"idempot|Idempotency", text, re.I):
        line_no = next((i for i, l in enumerate(ctx.lines, 1) if "@Retryable" in l), 1)
        out.append(
            CandidateFinding(
                risk_id=rid,
                line_start=line_no,
                line_end=line_no,
                snippet=_snippet(ctx, line_no, line_no),
                matched_signals=["retry_without_idempotency_key"],
                initial_reason="@Retryable present without obvious idempotency clues in file.",
                evidence={},
            )
        )
    return out


# --- RISK_15 ---
def _detect_risk_15(rules: dict[str, RiskRule], ctx: ScanContext) -> list[CandidateFinding]:
    rid = "RISK_15"
    if rid not in rules:
        return []
    out: list[CandidateFinding] = []
    rmw = re.compile(r"(\w+)\s*=\s*\w+\.findById\s*\([^)]+\)[^;]*;\s*[^\n]*\1\.set\w+\s*\(")
    blob = "".join(ctx.stripped_lines)
    if rmw.search(blob.replace("\n", " ")):
        out.append(
            CandidateFinding(
                risk_id=rid,
                line_start=1,
                line_end=min(5, len(ctx.lines)),
                snippet=_snippet(ctx, 1, min(5, len(ctx.lines))),
                matched_signals=["read_modify_write_pattern"],
                initial_reason="Possible read-modify-write without @Version in nearby text (very weak).",
                evidence={},
            )
        )
    return out


# --- RISK_16 ---
def _detect_risk_16(rules: dict[str, RiskRule], ctx: ScanContext) -> list[CandidateFinding]:
    rid = "RISK_16"
    if rid not in rules:
        return []
    out: list[CandidateFinding] = []
    for i, raw in enumerate(ctx.stripped_lines, start=1):
        if re.search(r"@RequestBody\s+Map\s*<", raw) or re.search(r"@RequestBody\s+Object\b", raw):
            out.append(
                CandidateFinding(
                    risk_id=rid,
                    line_start=i,
                    line_end=i,
                    snippet=_snippet(ctx, i, i),
                    matched_signals=["map_get_without_validation"],
                    initial_reason="@RequestBody Map/Object — validate at boundary (weak heuristic).",
                    evidence={"line": raw.strip()[:400]},
                )
            )
        elif re.search(r"@PathVariable\s+String\s+\w+", raw) and "@Valid" not in "".join(ctx.stripped_lines[max(0, i - 3) : i]):
            out.append(
                CandidateFinding(
                    risk_id=rid,
                    line_start=i,
                    line_end=i,
                    snippet=_snippet(ctx, i, i),
                    matched_signals=["request_param_direct_use"],
                    initial_reason="Path variable without obvious @Valid on a DTO nearby.",
                    evidence={"line": raw.strip()[:400]},
                )
            )
    return out


# --- RISK_17 ---
def _detect_risk_17(rules: dict[str, RiskRule], ctx: ScanContext) -> list[CandidateFinding]:
    rid = "RISK_17"
    if rid not in rules:
        return []
    out: list[CandidateFinding] = []
    pat = re.compile(r"\.findAll\s*\(\s*\)|\.list\s*\(\s*\)")
    for i, raw in enumerate(ctx.stripped_lines, start=1):
        if pat.search(raw) and "Pageable" not in raw and "Page<" not in raw:
            out.append(
                CandidateFinding(
                    risk_id=rid,
                    line_start=i,
                    line_end=i,
                    snippet=_snippet(ctx, i, i),
                    matched_signals=["find_all_call"],
                    initial_reason="findAll/list without pagination in same line (may still be bounded).",
                    evidence={"line": raw.strip()[:400]},
                )
            )
    return out


# --- RISK_18 ---
def _detect_risk_18(rules: dict[str, RiskRule], ctx: ScanContext) -> list[CandidateFinding]:
    rid = "RISK_18"
    if rid not in rules:
        return []
    out: list[CandidateFinding] = []
    for i, raw in enumerate(ctx.stripped_lines, start=1):
        if not re.search(r"\bfor\s*\(", raw):
            continue
        window = "".join(ctx.stripped_lines[i - 1 : min(len(ctx.lines), i + 20)])
        if re.search(r"\b\w+Repository\.\w+\(", window) or re.search(
            r"\.(get|post|exchange)\s*\(", window
        ):
            out.append(
                CandidateFinding(
                    risk_id=rid,
                    line_start=i,
                    line_end=i,
                    snippet=_snippet(ctx, i, min(len(ctx.lines), i + 8)),
                    matched_signals=["repo_call_in_loop"],
                    initial_reason="Possible N+1: repository or HTTP call inside loop context.",
                    evidence={"excerpt": window[:900]},
                )
            )
    return out


# --- RISK_19 ---
def _detect_risk_19(rules: dict[str, RiskRule], ctx: ScanContext) -> list[CandidateFinding]:
    rid = "RISK_19"
    if rid not in rules:
        return []
    out: list[CandidateFinding] = []
    risky = re.compile(r"@Async|@Retryable|CompletableFuture|RestTemplate|WebClient", re.I)
    log_hint = re.compile(r"\b(log|logger|slf4j|MeterRegistry|Tracer|Observation)\b", re.I)
    text = "".join(ctx.lines)
    if not risky.search(text):
        return []
    for i, raw in enumerate(ctx.stripped_lines, start=1):
        if risky.search(raw) and not log_hint.search("".join(ctx.stripped_lines[max(0, i - 5) : i + 8])):
            out.append(
                CandidateFinding(
                    risk_id=rid,
                    line_start=i,
                    line_end=i,
                    snippet=_snippet(ctx, i, i),
                    matched_signals=["risky_path_no_log"],
                    initial_reason="Risky integration/async construct with weak logging/metrics clues nearby.",
                    evidence={"line": raw.strip()[:400]},
                )
            )
    return out[:20]


# --- RISK_20 ---
def _detect_risk_20(rules: dict[str, RiskRule], ctx: ScanContext) -> list[CandidateFinding]:
    rid = "RISK_20"
    if rid not in rules:
        return []
    out: list[CandidateFinding] = []
    pat = re.compile(r"new\s+LinkedBlockingQueue\s*\(\s*\)|new\s+LinkedBlockingDeque\s*\(\s*\)")
    for i, raw in enumerate(ctx.stripped_lines, start=1):
        if pat.search(raw):
            out.append(
                CandidateFinding(
                    risk_id=rid,
                    line_start=i,
                    line_end=i,
                    snippet=_snippet(ctx, i, i),
                    matched_signals=["unbounded_blocking_queue"],
                    initial_reason="Unbounded queue may grow without limit under load.",
                    evidence={"line": raw.strip()[:400]},
                )
            )
    for i, raw in enumerate(ctx.stripped_lines, start=1):
        if "CacheBuilder.newBuilder" in raw:
            win = "".join(ctx.stripped_lines[i - 1 : min(len(ctx.lines), i + 12)])
            if "maximumSize" not in win and "maximumWeight" not in win:
                out.append(
                    CandidateFinding(
                        risk_id=rid,
                        line_start=i,
                        line_end=i,
                        snippet=_snippet(ctx, i, i),
                        matched_signals=["unbounded_cache"],
                        initial_reason="Guava CacheBuilder chain without maximumSize/Weight in nearby lines.",
                        evidence={"excerpt": win[:500]},
                    )
                )
    return out
