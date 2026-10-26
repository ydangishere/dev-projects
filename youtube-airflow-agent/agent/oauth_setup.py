"""One-time LOCAL OAuth authorization on the channel owner's PC.

Before running: Google Cloud -> OAuth consent screen -> configure test users if
app is in Testing -> Credentials -> Create OAuth client ID -> Desktop app.
Download JSON to secrets/client_secret.json (never commit it).
Run: python -m agent.oauth_setup
"""
from __future__ import annotations

import json
import secrets
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"


def main() -> None:
    secret_dir = Path(__file__).resolve().parents[1] / "secrets"
    client_path = secret_dir / "client_secret.json"
    if not client_path.exists():
        raise SystemExit("Put your Google Desktop OAuth JSON in secrets/client_secret.json")
    data = json.loads(client_path.read_text(encoding="utf-8"))
    client = data.get("installed")
    if not isinstance(client, dict):
        raise SystemExit("Create a Desktop OAuth client, not a web application client")
    state = secrets.token_urlsafe(32)
    received: dict[str, str] = {}

    class Callback(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if query.get("state", [""])[0] != state:
                self.send_error(400, "OAuth state mismatch")
                return
            if "error" in query:
                received["error"] = query["error"][0]
            else:
                received["code"] = query.get("code", [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"YouTube authorization completed. Return to PowerShell.")
        def log_message(self, *args) -> None:
            pass

    with HTTPServer(("127.0.0.1", 0), Callback) as server:
        server.timeout = 180
        redirect = "http://127.0.0.1:" + str(server.server_port) + "/"
        query = urllib.parse.urlencode({
            "client_id": client["client_id"], "redirect_uri": redirect,
            "response_type": "code", "scope": SCOPE,
            "state": state, "access_type": "offline", "prompt": "consent",
        })
        print("Opening Google authorization. Choose the account that owns @ydang7076.")
        webbrowser.open(AUTH_URL + "?" + query)
        server.handle_request()
    if received.get("error"):
        raise SystemExit("Google authorization declined: " + received["error"])
    if not received.get("code"):
        raise SystemExit("Authorization timed out or failed; run setup again.")
    body = urllib.parse.urlencode({
        "code": received["code"], "client_id": client["client_id"],
        "client_secret": client["client_secret"],
        "redirect_uri": redirect, "grant_type": "authorization_code",
    }).encode("utf-8")
    request = urllib.request.Request(TOKEN_URL, data=body, headers={
        "Content-Type": "application/x-www-form-urlencoded",
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        token = json.load(response)
    if not token.get("refresh_token"):
        raise SystemExit("No refresh token returned; revoke prior grant and repeat consent.")
    destination = secret_dir / "youtube_oauth.json"
    secret_dir.mkdir(exist_ok=True)
    destination.write_text(json.dumps({
        "client_id": client["client_id"],
        "client_secret": client["client_secret"],
        "refresh_token": token["refresh_token"],
    }, indent=2), encoding="utf-8")
    print("Saved secrets/youtube_oauth.json locally. NEVER upload this directory to GitHub.")


if __name__ == "__main__":
    main()
