"""Application-level encryption at rest for sensitive SQLite columns.

AES-256-GCM per value with a random 96-bit nonce. The row ID and column name are bound
as associated data, so a ciphertext copied to another row or column fails to decrypt.
Tenant, IDs and kinds stay plaintext because queries filter on them.

Keys: DATA_ENCRYPTION_KEY is the current base64 32-byte key used for new writes.
DATA_ENCRYPTION_OLD_KEYS (comma-separated) are accepted for reads during rotation;
scripts/rotate_keys.py re-encrypts every row with the current key. Each value records
the 8-hex key ID it was written with. Without a key, values are stored as before
(plaintext) and production startup refuses to run.
"""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

PREFIX = b"enc1:"


def _key(value: str) -> bytes:
    raw = base64.b64decode(value.strip(), validate=True)
    if len(raw) != 32:
        raise ValueError("Encryption keys must be base64 for exactly 32 bytes")
    return raw


def key_id(key: bytes) -> str:
    return hashlib.sha256(key).hexdigest()[:8]


def new_key() -> str:
    return base64.b64encode(os.urandom(32)).decode()


class Cipher:
    def __init__(self, current: str | None = None, old: str | None = None):
        self.current = _key(current) if current else None
        self.keys = {}
        for value in [current or "", *(old or "").split(",")]:
            if value.strip():
                key = _key(value)
                self.keys[key_id(key)] = key

    @classmethod
    def from_env(cls) -> "Cipher":
        return cls(os.getenv("DATA_ENCRYPTION_KEY"), os.getenv("DATA_ENCRYPTION_OLD_KEYS"))

    @property
    def enabled(self) -> bool:
        return self.current is not None

    def seal(self, data: bytes, aad: str) -> bytes:
        if not self.current:
            return data
        nonce = os.urandom(12)
        sealed = AESGCM(self.current).encrypt(nonce, data, aad.encode())
        return PREFIX + key_id(self.current).encode() + b":" + nonce + sealed

    def open(self, data: bytes, aad: str) -> bytes:
        # Without keys nothing was sealed, so a value that merely starts with the
        # prefix (for example uploaded text) is plaintext. Plaintext rows with keys
        # configured are legacy rows from before encryption; rotate_keys.py seals them.
        if not self.keys or not data.startswith(PREFIX):
            return data
        kid, body = data[len(PREFIX) : len(PREFIX) + 8].decode(), data[len(PREFIX) + 9 :]
        key = self.keys.get(kid)
        if not key:
            raise ValueError("No key available for encrypted value")
        return AESGCM(key).decrypt(body[:12], body[12:], aad.encode())

    def seal_text(self, text: str, aad: str) -> str:
        if not self.current:
            return text
        return "b64:" + base64.b64encode(self.seal(text.encode(), aad)).decode()

    def open_text(self, text: str, aad: str) -> str:
        if not text.startswith("b64:"):
            return text
        return self.open(base64.b64decode(text[4:]), aad).decode()

    def is_current(self, data: bytes | str) -> bool:
        if isinstance(data, str):
            if not data.startswith("b64:"):
                return not self.current
            data = base64.b64decode(data[4:])
        if not data.startswith(PREFIX):
            return not self.current
        return bool(self.current) and data[len(PREFIX) : len(PREFIX) + 8].decode() == key_id(
            self.current
        )
