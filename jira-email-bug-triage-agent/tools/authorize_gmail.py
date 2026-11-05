"""Optional user-approved Gmail readonly OAuth flow; never used by default."""
import argparse
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPE = ["https://www.googleapis.com/auth/gmail.readonly"]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--token", type=Path, required=True)
    args = parser.parse_args()
    args.token.parent.mkdir(parents=True, exist_ok=True)
    flow = InstalledAppFlow.from_client_secrets_file(str(args.credentials), SCOPE)
    credentials = flow.run_local_server(port=0)
    args.token.write_text(credentials.to_json(),encoding="utf-8")
    args.token.chmod(0o600)
    print("Gmail readonly authorization saved locally. Do not commit this file.")

if __name__ == "__main__":
    main()
