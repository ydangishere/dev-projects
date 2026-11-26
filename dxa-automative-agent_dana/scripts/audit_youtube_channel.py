"""Audit public YouTube videos/Shorts/live against the current DXA knowledge.

Read-only: never downloads media or changes DXA knowledge files.
Run: pip install -U yt-dlp ; python scripts/audit_youtube_channel.py
"""
import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from yt_dlp import YoutubeDL

ROOT = Path(__file__).resolve().parents[1]
CHANNEL = "https://www.youtube.com/@ydang7076"
TABS = {"videos": CHANNEL + "/videos", "shorts": CHANNEL + "/shorts", "streams": CHANNEL + "/streams"}
OUT = ROOT / "reports"
OUT.mkdir(exist_ok=True)
found = {}
status = {}
opts = {
    "extract_flat": "in_playlist", "skip_download": True, "quiet": True,
    "no_warnings": True, "ignoreerrors": True,
    "socket_timeout": 25, "retries": 2, "extractor_retries": 2,
}
for category, url in TABS.items():
    print(f"[youtube inventory] scanning {category}: {url}", flush=True)
    try:
        extraction_errors = []

        class Logger:
            def debug(self, message):
                pass

            def warning(self, message):
                pass

            def error(self, message):
                extraction_errors.append(str(message))

        with YoutubeDL({**opts, "logger": Logger()}) as ydl:
            info = ydl.extract_info(url, download=False)
        if not info or "entries" not in info:
            absent = f"does not have a {category} tab"
            if extraction_errors and all(absent in error for error in extraction_errors):
                status[category] = {"count": 0, "status": "ok", "note": f"no public {category} tab"}
                print(f"[youtube inventory] {category}=0 (no public tab)", flush=True)
                continue
            raise ValueError("YouTube did not return a playlist: " + "; ".join(extraction_errors)[:150])
        seen_in_category = set()
        for item in info["entries"]:
            if not item:
                continue
            vid = item.get("id") or ""
            if not re.fullmatch(r"[a-zA-Z0-9_-]{11}", vid):
                continue
            seen_in_category.add(vid)
            if vid not in found:
                found[vid] = {
                    "video_id": vid,
                    "title": item.get("title") or "",
                    "url": f"https://www.youtube.com/watch?v={vid}",
                    "categories": category,
                    "release_date": str(item.get("release_date") or item.get("upload_date") or ""),
                }
            elif category not in found[vid]["categories"].split(","):
                found[vid]["categories"] += "," + category
        count = len(seen_in_category)
        status[category] = {"count": count, "status": "failed" if extraction_errors else "ok"}
        if extraction_errors:
            status[category]["error"] = "; ".join(extraction_errors)[:300]
        print(f"[youtube inventory] {category}={count}", flush=True)
    except Exception as exc:
        status[category] = {"count": None, "status": "failed", "error": type(exc).__name__ + ": " + str(exc)[:150]}
        print(f"[youtube inventory] ERROR {category}: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)

with (ROOT / "data" / "videos.tsv").open(encoding="utf-8", newline="") as f:
    tracked = list(csv.DictReader(f, delimiter="\t"))
tracked_ids = {row["video_id"] for row in tracked}
tracked_by_id = {row["video_id"]: row for row in tracked}
case_counts = Counter()
for path in (ROOT / "data").glob("knowledge*.json"):
    for case in json.loads(path.read_text(encoding="utf-8")).get("cases", []):
        if case.get("status") != "rejected" and case.get("video_id"):
            case_counts[case["video_id"]] += 1
for item in found.values():
    vid = item["video_id"]
    clean = ROOT / "data" / "clean" / (vid + ".txt")
    segments = sum(bool(re.match(r"^\[\d+\]\s*\S", line)) for line in clean.read_text(encoding="utf-8").splitlines()) if clean.exists() else 0
    listed = tracked_by_id.get(vid)
    item["in_dxa"] = "yes" if listed else "no"
    item["in_dxa_knowledge"] = "yes" if segments or case_counts[vid] else "no"
    item["curation_status"] = listed["status"] if listed else ""
    item["transcript_segments"] = segments
    item["active_cases"] = case_counts[vid]
    item["coverage_status"] = ("in_knowledge" if item["in_dxa_knowledge"] == "yes" else
                               "previously_skipped" if listed and listed["status"].startswith("bo_qua") else
                               "listed_without_knowledge" if listed else "not_yet_processed")

fields = ["video_id", "title", "url", "categories", "release_date", "in_dxa", "in_dxa_knowledge",
          "curation_status", "transcript_segments", "active_cases", "coverage_status"]
rows = sorted(found.values(), key=lambda x: (x["categories"], x["title"]))
for name, selected in [
    ("youtube_channel_inventory.csv", rows), ("youtube_source_coverage.csv", rows),
    ("youtube_unused_videos.csv", [r for r in rows if r["coverage_status"] == "not_yet_processed"]),
    ("youtube_listed_but_unused.csv", [r for r in rows if r["coverage_status"] == "previously_skipped"]),
]:
    with (OUT / name).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(selected)
report = {
    "channel": CHANNEL, "scanned_at_utc": datetime.now(timezone.utc).isoformat(),
    "tabs": status, "unique_public_video_ids_seen": len(found),
    "dxa_listed": len(tracked), "dxa_ids_found_in_scan": len(tracked_ids & found.keys()),
    "missing_from_dxa_in_public_scan": len(found.keys() - tracked_ids),
    "example_eHyZh0emGG8_found": "eHyZh0emGG8" in found,
    "example_eHyZh0emGG8_in_dxa": "eHyZh0emGG8" in tracked_ids,
    "complete": all(x["status"] == "ok" for x in status.values()),
    "knowledge_coverage": dict(Counter(row["coverage_status"] for row in rows)),
}
(OUT / "youtube_channel_inventory_summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
print("AUDIT_YOUTUBE_SUMMARY=" + json.dumps(report, ensure_ascii=False), flush=True)
if not report["complete"]:
    raise SystemExit("INCOMPLETE: some YouTube tabs could not be scanned; do not report a definitive total")
