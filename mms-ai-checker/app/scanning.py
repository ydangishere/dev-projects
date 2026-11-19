"""Upload malware scanning through a ClamAV daemon (clamd INSTREAM protocol).

MALWARE_SCAN=off (default for local demo) skips scanning. MALWARE_SCAN=clamd sends
every uploaded file to clamd at CLAMD_HOST:CLAMD_PORT before it is stored. The scan
fails closed: if clamd is unreachable, times out or answers unexpectedly, the upload
is rejected. No third-party package is needed; the protocol is a plain TCP stream.

A clean verdict means the installed signatures found nothing. It is not proof that a
file is safe, and it does not replace isolated parsing or content disarm.
"""

from __future__ import annotations

import os
import socket
import struct
from dataclasses import dataclass

CHUNK = 64 * 1024


@dataclass
class Verdict:
    clean: bool
    signature: str | None
    engine: str


class ScanUnavailable(RuntimeError):
    pass


class ClamdScanner:
    name = "clamd"

    def __init__(self, host: str = "127.0.0.1", port: int = 3310, timeout: float = 30):
        self.host, self.port, self.timeout = host, port, timeout

    def _talk(self, payload: list[bytes]) -> str:
        try:
            with socket.create_connection((self.host, self.port), self.timeout) as conn:
                conn.settimeout(self.timeout)
                for part in payload:
                    conn.sendall(part)
                reply = b""
                while not reply.endswith(b"\0"):
                    block = conn.recv(4096)
                    if not block:
                        break
                    reply += block
                    if len(reply) > 4096:
                        break
        except OSError as error:
            raise ScanUnavailable("Malware scanner unreachable") from error
        return reply.rstrip(b"\0").decode("utf-8", "replace").strip()

    def ping(self) -> bool:
        try:
            return self._talk([b"zPING\0"]) == "PONG"
        except ScanUnavailable:
            return False

    def scan(self, data: bytes) -> Verdict:
        payload = [b"zINSTREAM\0"]
        for start in range(0, len(data), CHUNK):
            block = data[start : start + CHUNK]
            payload.append(struct.pack(">I", len(block)) + block)
        payload.append(struct.pack(">I", 0))
        reply = self._talk(payload)
        if reply == "stream: OK":
            return Verdict(True, None, self.name)
        if reply.startswith("stream: ") and reply.endswith(" FOUND"):
            return Verdict(False, reply[len("stream: ") : -len(" FOUND")], self.name)
        # Size-limit errors, unknown replies and empty replies are all failures.
        raise ScanUnavailable("Unexpected scanner reply")


def build_scanner(mode: str | None = None):
    mode = (mode or os.getenv("MALWARE_SCAN", "off")).casefold()
    if mode == "off":
        return None
    if mode == "clamd":
        return ClamdScanner(
            os.getenv("CLAMD_HOST", "127.0.0.1"),
            int(os.getenv("CLAMD_PORT", "3310")),
            float(os.getenv("CLAMD_TIMEOUT", "30")),
        )
    raise ValueError("MALWARE_SCAN must be off or clamd")
