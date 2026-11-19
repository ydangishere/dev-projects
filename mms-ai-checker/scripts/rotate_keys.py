"""Encrypt legacy rows or rotate the data-at-rest key.

  python scripts/rotate_keys.py --new-key            print a fresh base64 key
  python scripts/rotate_keys.py                      re-seal all rows with DATA_ENCRYPTION_KEY

Rotation: set DATA_ENCRYPTION_KEY to the new key and DATA_ENCRYPTION_OLD_KEYS to the
previous key(s), run this script, then remove the old key from configuration. Stop the
service (or accept that rows written mid-run use the new key, which is also correct)
and back up DATA_DIR first. Run VACUUM afterwards so freed pages with old plaintext or
old ciphertext are dropped from the file.
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.crypto import Cipher, new_key  # noqa: E402
from app.store import Store  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--new-key", action="store_true", help="print a new key and exit")
parser.add_argument("--data-dir", default=None)
args = parser.parse_args()
if args.new_key:
    print(new_key())
    raise SystemExit
load_dotenv(ROOT / ".env")
cipher = Cipher.from_env()
directory = args.data_dir or os.getenv("DATA_DIR", str(ROOT / "runtime"))
store = Store(directory, cipher)
changed = store.rotate()
with sqlite3.connect(store.path) as db:
    db.execute("VACUUM")
state = "encrypted with the current key" if cipher.enabled else "decrypted to plaintext"
print(f"{changed} values re-sealed; all sensitive values are {state}.")
