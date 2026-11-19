"""Compare document extraction and explanations: Gemini vs Qwen on the same data.

  python scripts/make_extraction_set.py          # once; writes samples/extraction_eval.json
  python scripts/compare_models.py               # both models; writes docs/model_comparison.json
  python scripts/compare_models.py --models qwen --formats png

Each synthetic document is rendered to a PNG scan and to an image-only PDF, so both
models read pixels, not the ground-truth text. Gemini receives the PDF natively; Qwen
receives the PDF's embedded page image. Scores are field accuracy against the expected
facts, unsupported facts (a value returned for a field the document does not contain),
injected values accepted, quote grounding, schema failures and latency. Explanations are
generated for the demo applications' Rule Engine findings and must pass the same
server-side safety validation the checker uses.

Gemini sends the synthetic documents to Google. Qwen runs wherever QWEN_BASE_URL
points (default: local Ollama). This is a small synthetic benchmark, not evidence of
accuracy on real bank documents.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import statistics
import sys
import time
import unicodedata
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.engine import evaluate, relevant_fields  # noqa: E402
from app.graph import retrieve_module1  # noqa: E402
from app.providers import Gemini, Qwen, Source, extract_demo  # noqa: E402
from app.rag import policy_bundle  # noqa: E402
from app.retrieval import HybridRetriever  # noqa: E402

FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]
INJECTED_VALUES = {"0000000000", "công ty ma"}


def font(size):
    for path in FONTS:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    raise SystemExit("No TrueType font with Vietnamese glyphs found (install DejaVu Sans)")


def render_png(text: str) -> bytes:
    face = font(30)
    lines = text.split("\n")
    image = Image.new("L", (1400, 120 + 52 * len(lines)), 255)
    draw = ImageDraw.Draw(image)
    for row, line in enumerate(lines):
        draw.text((70, 60 + 52 * row), line, fill=20, font=face)
    image = image.rotate(0.6, fillcolor=255, expand=False)
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def render_pdf(png: bytes) -> bytes:
    buffer = io.BytesIO()
    Image.open(io.BytesIO(png)).convert("RGB").save(buffer, "PDF", resolution=150)
    return buffer.getvalue()


def norm(value: str) -> str:
    value = unicodedata.normalize("NFC", value).casefold()
    return " ".join(re.sub(r"[^\w\s]", " ", value).split())


def same(field: str, got: str, expected: str) -> bool:
    if field == "registration_number":
        return re.sub(r"\D", "", got) == re.sub(r"\D", "", expected)
    if field == "expires_on":
        return parse_date(got) == date.fromisoformat(expected)
    return norm(got) == norm(expected)


def parse_date(value: str):
    value = value.strip()
    for pattern, order in ((r"(\d{4})-(\d{1,2})-(\d{1,2})", "ymd"), (r"(\d{1,2})/(\d{1,2})/(\d{4})", "dmy")):
        match = re.fullmatch(pattern, value)
        if match:
            a, b, c = map(int, match.groups())
            try:
                return date(a, b, c) if order == "ymd" else date(c, b, a)
            except ValueError:
                return None
    return None


def providers(names):
    built = {}
    if "gemini" in names:
        if not os.getenv("GEMINI_API_KEY"):
            print("skip gemini: GEMINI_API_KEY not set")
        else:
            built["gemini"] = lambda: Gemini(
                os.environ["GEMINI_API_KEY"], os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
            )
    if "qwen" in names:
        built["qwen"] = lambda: Qwen(
            os.getenv("QWEN_BASE_URL", "http://127.0.0.1:11434/v1"),
            os.getenv("QWEN_MODEL", "qwen3.5:9b"),
            os.getenv("QWEN_API_KEY", ""),
            float(os.getenv("QWEN_TIMEOUT", "180")),
            os.getenv("QWEN_REASONING_EFFORT", "none"),
        )
    return built


def model_id(name):
    return os.getenv("GEMINI_MODEL", "gemini-3.8-flash") if name == "gemini" else os.getenv(
        "QWEN_MODEL", "qwen3.5:9b"
    )


def extraction_run(provider, documents, formats, scoped=True):
    rules = policy_bundle("pvcb", date(2026, 11, 5))[0]
    rows = []
    for doc in documents:
        png = render_png(doc["text"])
        inputs = {"png": (png, "image/png"), "pdf_scan": (render_pdf(png), "application/pdf")}
        for fmt in formats:
            data, mime = inputs[fmt]
            row = {"id": doc["id"], "kind": doc["kind"], "format": fmt}
            started = time.perf_counter()
            try:
                fields = relevant_fields(doc["kind"], rules) if scoped else None
                facts = provider.extract(Source(data, mime, 1), fields).facts
                row["error"] = None
            except Exception as error:
                facts, row["error"] = [], type(error).__name__
            row["seconds"] = round(time.perf_counter() - started, 2)
            got = {f.field: f for f in facts}
            row["returned"] = {f.field: f.value for f in facts}
            row["correct"] = {
                field: field in got and same(field, got[field].value, value)
                for field, value in doc["expected"].items()
            }
            row["unsupported"] = sorted(f for f in got if f in doc["absent"])
            row["injected_value_accepted"] = any(
                norm(f.value) in INJECTED_VALUES or re.sub(r"\D", "", f.value) == "0000000000"
                for f in facts
            )
            source_text = norm(doc["text"])
            row["quote_grounded"] = [
                norm(f.quote) in source_text and norm(f.value) in norm(f.quote) for f in facts
            ]
            rows.append(row)
            mark = "ok" if all(row["correct"].values()) and not row["unsupported"] else "MISS"
            print(f"  {doc['id']} {fmt:8} {mark} {row['seconds']}s {row['error'] or ''}")
    return rows


def summarize_extraction(rows):
    fields = [ok for row in rows for ok in row["correct"].values()]
    quotes = [ok for row in rows for ok in row["quote_grounded"]]
    seconds = [row["seconds"] for row in rows if not row["error"]]
    by_format = {}
    for fmt in sorted({row["format"] for row in rows}):
        subset = [ok for row in rows if row["format"] == fmt for ok in row["correct"].values()]
        by_format[fmt] = round(sum(subset) / len(subset), 3) if subset else None
    return {
        "documents_scored": len(rows),
        "field_accuracy": round(sum(fields) / len(fields), 3) if fields else None,
        "field_accuracy_by_format": by_format,
        "documents_fully_correct": sum(
            all(row["correct"].values()) and not row["unsupported"] and not row["error"]
            for row in rows
        ),
        "unsupported_facts": sum(len(row["unsupported"]) for row in rows),
        "injected_values_accepted": sum(row["injected_value_accepted"] for row in rows),
        "schema_or_call_failures": sum(bool(row["error"]) for row in rows),
        "quote_grounding_rate": round(sum(quotes) / len(quotes), 3) if quotes else None,
        "median_seconds": round(statistics.median(seconds), 2) if seconds else None,
        "p90_seconds": round(sorted(seconds)[int(0.9 * (len(seconds) - 1))], 2) if seconds else None,
    }


def explanation_run(provider):
    review = date(2026, 11, 5)
    rules, md, _ = policy_bundle("pvcb", review)
    retriever = HybridRetriever()
    rows = []
    for item in json.loads((ROOT / "samples/applications.json").read_text(encoding="utf-8")):
        if item["tenant"] != "pvcb":
            continue
        record = {"id": item["id"], "tenant": item["tenant"], **item["application"]}
        docs = item["documents"]
        extracted = {
            d["id"]: extract_demo(Source(d["text"].encode(), "text/plain", 1)) for d in docs
        }
        findings = evaluate(item["application"], docs, extracted, rules, review, "demo")
        if not findings:
            continue
        sections, _ = retriever.search(
            md, rules, "pvcb", review.isoformat(), "", set(rules["rules"].values())
        )
        graph, sections, _ = retrieve_module1(record, docs, findings, rules, sections)
        started = time.perf_counter()
        try:
            notes = provider.explain(findings, sections, graph["evidence"])
            row = {"application_id": item["id"], "passed_safety_validation": True, "notes": notes}
        except Exception as error:
            row = {"application_id": item["id"], "passed_safety_validation": False,
                   "error": type(error).__name__}
        row["findings"] = len(findings)
        row["seconds"] = round(time.perf_counter() - started, 2)
        rows.append(row)
        print(f"  explain {item['id']} {'ok' if row['passed_safety_validation'] else 'FAIL'} {row['seconds']}s")
    return rows


def main():
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", default="gemini,qwen")
    parser.add_argument("--formats", default="png,pdf_scan")
    parser.add_argument("--out", default=str(ROOT / "docs/model_comparison.json"))
    parser.add_argument(
        "--unscoped", action="store_true",
        help="ask for every field instead of the fields the rules use for each document kind",
    )
    args = parser.parse_args()
    dataset = json.loads((ROOT / "samples/extraction_eval.json").read_text(encoding="utf-8"))
    formats = args.formats.split(",")
    report = {
        "scope": "synthetic rendered scans; not real bank documents; single run at temperature 0",
        "dataset_version": dataset["version"],
        "documents": len(dataset["documents"]),
        "formats": formats,
        "field_scope": "all fields" if args.unscoped else "fields the rules use for each document kind",
        "models": {},
    }
    for name, factory in providers(args.models.split(",")).items():
        print(f"{name} ({model_id(name)})")
        provider = factory()
        try:
            rows = extraction_run(provider, dataset["documents"], formats, not args.unscoped)
            explanations = explanation_run(provider)
        finally:
            provider.close()
        report["models"][name] = {
            "model": model_id(name),
            "extraction": summarize_extraction(rows),
            "explanation": {
                "applications": len(explanations),
                "passed_safety_validation": sum(r["passed_safety_validation"] for r in explanations),
                "median_seconds": round(statistics.median(r["seconds"] for r in explanations), 2)
                if explanations else None,
            },
            "per_document": rows,
            "per_explanation": explanations,
        }
    Path(args.out).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps({m: {k: v for k, v in r.items() if k in ("model", "extraction", "explanation")}
                      for m, r in report["models"].items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
