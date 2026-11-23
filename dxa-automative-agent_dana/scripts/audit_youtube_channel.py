"""Audit public YouTube channel videos/Shorts/live and compare with DXA's 30 curated entries.

Read-only: never downloads media or changes DXA knowledge files.
Run: pip install -U yt-dlp ; python scripts/audit_youtube_channel.py
"""
import csv
import json
import re
import sys
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
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        if not info or "entries" not in info:
            raise ValueError("YouTube did not return a playlist")
        count = 0
        for item in info["entries"]:
            if not item:
                continue
            vid = item.get("id") or ""
            if not re.fullmatch(r"[a-zA-Z0-9_-]{11}", vid):
                continue
            count += 1
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
        status[category] = {"count": count, "status": "ok"}
        print(f"[youtube inventory] {category}={count}", flush=True)
    except Exception as exc:
        status[category] = {"count": None, "status": "failed", "error": type(exc).__name__ + ": " + str(exc)[:150]}
        print(f"[youtube inventory] ERROR {category}: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)

with (ROOT / "data" / "videos.tsv").open(encoding="utf-8", newline="") as f:
    tracked = list(csv.DictReader(f, delimiter="\t"))
tracked_ids = {row["video_id"] for row in tracked}
for item in found.values():
    item["in_dxa"] = "yes" if item["video_id"] in tracked_ids else "no"

with (OUT / "youtube_channel_inventory.csv").open("w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["video_id", "title", "url", "categories", "release_date", "in_dxa"])
    writer.writeheader()
    writer.writerows(sorted(found.values(), key=lambda x: (x["categories"], x["title"])))
report = {
    "channel": CHANNEL, "scanned_at_utc": datetime.now(timezone.utc).isoformat(),
    "tabs": status, "unique_public_video_ids_seen": len(found),
    "dxa_listed": len(tracked), "dxa_ids_found_in_scan": len(tracked_ids & found.keys()),
    "missing_from_dxa_in_public_scan": len(found.keys() - tracked_ids),
    "example_eHyZh0emGG8_found": "eHyZh0emGG8" in found,
    "example_eHyZh0emGG8_in_dxa": "eHyZh0emGG8" in tracked_ids,
    "complete": all(x["status"] == "ok" for x in status.values()),
}
(OUT / "youtube_channel_inventory_summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
print("AUDIT_YOUTUBE_SUMMARY=" + json.dumps(report, ensure_ascii=False), flush=True)
if not report["complete"]:
    raise SystemExit("INCOMPLETE: some YouTube tabs could not be scanned; do not report a definitive total")
