"""Opt-in, human-approved FAQ replies for YouTube top-level public comments.

Uses fixed owner-approved replies, not free-form model-generated public text.
Requires an OAuth refresh token; an ordinary YouTube API key is read-only.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import unicodedata
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from agent.monitor import API_BASE, request_json

LOG = logging.getLogger(__name__)
TOKEN_URL = "https://oauth2.googleapis.com/token"


def enabled() -> bool:
    return os.getenv("AUTO_REPLY_ENABLED", "false").lower() == "true"


def dry_run() -> bool:
    return os.getenv("AUTO_REPLY_DRY_RUN", "true").lower() != "false"


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").casefold()
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def load_rules(path: str | None = None) -> list[dict[str, Any]]:
    path = path or os.getenv("AUTO_REPLY_FAQ_PATH", "/opt/airflow/config/faq_rules.json")
    p = Path(path)
    if not p.is_file():
        LOG.warning("No FAQ file at %s. Auto-reply rules are empty.", path)
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    rules = data.get("rules", []) if isinstance(data, dict) else None
    if not isinstance(rules, list):
        raise ValueError("FAQ file must contain a 'rules' array")
    result = []
    known_ids = set()
    for entry in rules:
        if not isinstance(entry, dict):
            raise ValueError("Each FAQ rule must be an object")
        rule_id, answer, triggers = entry.get("id"), entry.get("reply"), entry.get("triggers")
        if (not isinstance(rule_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,45}", rule_id)
            or rule_id in known_ids or not isinstance(answer, str) or not answer.strip()
            or len(answer) > 600 or not isinstance(triggers, list) or not triggers):
            raise ValueError("Invalid FAQ rule; supply a unique id, nonempty reply <=600 chars, and triggers")
        if not all(isinstance(t, str) and len(normalize(t)) >= 6 for t in triggers):
            raise ValueError("Each trigger must contain at least six normalized characters")
        known_ids.add(rule_id)
        result.append({"id": rule_id, "reply": answer.strip(),
                       "triggers": [normalize(t) for t in triggers]})
    return result


def find_rule(text: str, rules: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Conservative literal-phrase matching; ambiguous matches never auto-post."""
    source = " " + normalize(text) + " "
    matches = [r for r in rules if any((" " + phrase + " ") in source for phrase in r["triggers"])]
    return matches[0] if len(matches) == 1 else None


def register_attempts_table(conn: sqlite3.Connection) -> None:
    conn.execute("""CREATE TABLE IF NOT EXISTS reply_attempts (
        comment_id TEXT PRIMARY KEY, rule_id TEXT NOT NULL, status TEXT NOT NULL,
        recorded_at TEXT NOT NULL, reply_id TEXT
    )""")
    conn.commit()


def _oauth_access_token(credentials_path: str) -> str:
    credentials = json.loads(Path(credentials_path).read_text(encoding="utf-8"))
    required = ("client_id", "client_secret", "refresh_token")
    if any(not credentials.get(k) for k in required):
        raise ValueError("YouTube OAuth credentials require client_id, client_secret, refresh_token")
    # Refresh in memory on every run; no secret tokens are written to logs.
    import urllib.parse
    import urllib.request
    import urllib.error
    body = urllib.parse.urlencode({
        "client_id": credentials["client_id"],
        "client_secret": credentials["client_secret"],
        "refresh_token": credentials["refresh_token"],
        "grant_type": "refresh_token",
    }).encode("utf-8")
    request = urllib.request.Request(
        TOKEN_URL, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(request, timeout=35) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"YouTube OAuth token refresh failed: HTTP {exc.code}") from None
    token = data.get("access_token")
    if not token:
        raise RuntimeError("YouTube OAuth refresh did not return an access token")
    return str(token)


def post_reply(comment_id: str, reply: str, owner_channel_id: str, credentials_path: str) -> str:
    token = _oauth_access_token(credentials_path)
    headers = {"Authorization": "Bearer " + token}
    mine = request_json(f"{API_BASE}/channels", params={"part": "id", "mine": "true"}, headers=headers)
    if owner_channel_id not in [x.get("id") for x in mine.get("items", [])]:
        raise RuntimeError("OAuth Google account is not authorized for the configured YouTube channel")
    data = request_json(
        f"{API_BASE}/comments",
        params={"part": "snippet"},
        payload={"snippet": {"parentId": comment_id, "textOriginal": reply}},
        headers=headers,
    )
    if not data.get("id"):
        raise RuntimeError("YouTube did not confirm the posted reply")
    return str(data["id"])


def process_auto_reply(
    conn: sqlite3.Connection, comment: dict[str, str],
    owner_channel_id: str, rules: list[dict[str, Any]], attempts_this_run: int,
) -> dict[str, Any]:
    if not enabled() or comment.get("kind") != "top-level":
        return {"status": "skipped"}
    if comment.get("author_channel_id") == owner_channel_id:
        return {"status": "skipped"}
    if attempts_this_run >= max(0, min(20, int(os.getenv("AUTO_REPLY_MAX_PER_RUN", "3")))):
        return {"status": "limit"}
    from agent.monitor import parse_datetime, now_utc
    max_age = max(1, min(72, int(os.getenv("AUTO_REPLY_MAX_AGE_HOURS", "24"))))
    if parse_datetime(comment["published_at"]) < now_utc() - timedelta(hours=max_age):
        return {"status": "old"}
    rule = find_rule(comment.get("text", ""), rules)
    if not rule:
        return {"status": "no_faq"}
    register_attempts_table(conn)
    if conn.execute("SELECT 1 FROM reply_attempts WHERE comment_id=?", (comment["comment_id"],)).fetchone():
        return {"status": "duplicate"}
    if dry_run():
        LOG.info("DRY RUN: would reply to comment %s with FAQ rule %s", comment["comment_id"], rule["id"])
        return {"status": "dry_run", "rule": rule["id"]}
    path = os.getenv("YOUTUBE_OAUTH_FILE", "/opt/airflow/secrets/youtube_oauth.json")
    if not Path(path).is_file():
        LOG.warning("YouTube OAuth file missing: auto-reply not attempted")
        return {"status": "no_oauth"}
    # Reserve first. If the network fails after YouTube posts, do not retry blindly.
    conn.execute("INSERT OR IGNORE INTO reply_attempts(comment_id,rule_id,status,recorded_at) VALUES (?,?,?,?)",
                 (comment["comment_id"], rule["id"], "attempted", now_utc().isoformat()))
    conn.commit()
    try:
        reply_id = post_reply(comment["comment_id"], rule["reply"], owner_channel_id, path)
        conn.execute("UPDATE reply_attempts SET status='sent', reply_id=? WHERE comment_id=?",
                     (reply_id, comment["comment_id"]))
        conn.commit()
        LOG.info("Auto-replied to comment %s using FAQ %s", comment["comment_id"], rule["id"])
        return {"status": "sent", "rule": rule["id"]}
    except Exception:
        conn.execute("UPDATE reply_attempts SET status='error_needs_review' WHERE comment_id=?",
                     (comment["comment_id"],))
        conn.commit()
        LOG.exception("Auto-reply could not be confirmed. Review the comment manually; no automatic retry.")
        return {"status": "error_needs_review", "rule": rule["id"]}
