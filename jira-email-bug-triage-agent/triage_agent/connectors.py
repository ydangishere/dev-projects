"""Jira and Gmail source adapters. Default is sample-only, no credentials required."""
import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List

@dataclass(frozen=True)
class WorkItem:
    source: str
    external_id: str
    title: str
    description: str
    url: str = ""


def mock_items(path: Path) -> List[WorkItem]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [WorkItem(**v) for v in raw]


def jira_items(max_items: int = 100) -> List[WorkItem]:
    """Opt-in Jira Cloud REST read-only query. Set JIRA_* environment variables."""
    import requests  # optional, installed from requirements-connectors.txt
    from requests.auth import HTTPBasicAuth
    base = os.environ["JIRA_BASE_URL"].rstrip("/")
    if not base.startswith("https://"):
        raise ValueError("JIRA_BASE_URL must use HTTPS")
    auth = HTTPBasicAuth(os.environ["JIRA_EMAIL"], os.environ["JIRA_API_TOKEN"])
    jql = os.getenv("JIRA_JQL", 'issuetype in (Bug, Incident) ORDER BY updated DESC')
    rows: List[WorkItem] = []
    next_token = None
    while len(rows) < max_items:
        params = {"jql": jql, "maxResults": min(50, max_items-len(rows)),
                  "fields": "summary,description,issuetype,status,updated"}
        if next_token:
            params["nextPageToken"] = next_token
        res = requests.get(base+"/rest/api/3/search/jql", params=params, auth=auth,
                           headers={"Accept": "application/json"}, timeout=20)
        res.raise_for_status()
        page = res.json()
        for issue in page.get("issues", []):
            fields = issue.get("fields", {})
            desc = _adf_text(fields.get("description"))
            key = issue["key"]
            rows.append(WorkItem("jira", key, str(fields.get("summary", "")), desc,
                                 base+"/browse/"+key))
        next_token = page.get("nextPageToken")
        if not next_token or not page.get("issues"):
            break
    return rows


def _adf_text(value) -> str:
    """Extract plaintext recursively from Jira's Atlassian Document Format."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(_adf_text(v) for v in value)
    if isinstance(value, dict):
        chunks = [str(value["text"])] if isinstance(value.get("text"), str) else []
        chunks.extend(_adf_text(value.get("content", [] )).split("\n"))
        return " ".join(chunks)
    return ""


def gmail_items(max_items: int = 100) -> List[WorkItem]:
    """Opt-in Gmail API readonly OAuth. Never sends, archives, labels or deletes messages."""
    from google.oauth2.credentials import Credentials  # optional
    from googleapiclient.discovery import build  # optional
    token_path = Path(os.environ["GMAIL_TOKEN_FILE"])
    if not token_path.exists():
        raise FileNotFoundError("Obtain an OAuth readonly token locally; see README")
    creds = Credentials.from_authorized_user_file(str(token_path),
              scopes=["https://www.googleapis.com/auth/gmail.readonly"])
    if not creds.valid:
        raise RuntimeError("Gmail OAuth token expired; renew locally first")
    client = build("gmail", "v1", credentials=creds, cache_discovery=False)
    query = os.getenv("GMAIL_QUERY", "(bug OR incident OR error) newer_than:30d")
    result: List[WorkItem] = []
    token = None
    while len(result) < max_items:
        response = client.users().messages().list(userId="me", q=query,
              maxResults=min(100, max_items-len(result)), pageToken=token).execute()
        for entry in response.get("messages", []):
            message = client.users().messages().get(userId="me", id=entry["id"],
                          format="metadata", metadataHeaders=["Subject"]).execute()
            headers = message.get("payload", {}).get("headers", [])
            subject = next((h.get("value", "") for h in headers
                            if h.get("name", "").lower() == "subject"), "")
            result.append(WorkItem("email", message["id"], subject,
                      message.get("snippet", ""),
                      "https://mail.google.com/mail/u/0/#all/"+message["id"]))
        token = response.get("nextPageToken")
        if not token:
            break
    return result


def load_items(mode: str, fixture: Path, max_items: int) -> List[WorkItem]:
    if mode == "mock":
        return mock_items(fixture)[:max_items]
    if mode == "jira":
        return jira_items(max_items)
    if mode == "gmail":
        return gmail_items(max_items)
    if mode == "both":
        return jira_items(max_items//2) + gmail_items(max_items-max_items//2)
    raise ValueError("Choose mock, jira, gmail or both")
