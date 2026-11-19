"""Encryption at rest, malware scanning, OIDC SSO and metrics."""

import base64
import os
import socket
import sqlite3
import struct
import sys
import threading
import time
from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient

from app.auth import OIDCVerifier
from app.crypto import Cipher, new_key
from app.main import create_app
from app.scanning import ClamdScanner, ScanUnavailable
from app.store import Store

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from mock_idp import ROLE_MAP, MockIdP  # noqa: E402

CHECKER = {"Authorization": "Bearer demo-checker-token"}
MAKER = {"Authorization": "Bearer demo-maker-token"}
EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
SECURITY_ENV = [
    "TOKENS_JSON", "APP_ENV", "DATA_ENCRYPTION_KEY", "DATA_ENCRYPTION_OLD_KEYS",
    "MALWARE_SCAN", "CLAMD_HOST", "CLAMD_PORT", "AUTH_MODE", "METRICS_TOKEN",
    "OIDC_ISSUER", "OIDC_AUDIENCE", "OIDC_JWKS_URL", "OIDC_ROLE_MAP", "OIDC_ALLOWED_TENANTS",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in SECURITY_ENV:
        monkeypatch.delenv(name, raising=False)


# ---------------------------------------------------------------- encryption at rest


def test_cipher_round_trip_and_binds_row():
    cipher = Cipher(new_key())
    sealed = cipher.seal(b"secret bytes", "documents.data:a")
    assert sealed.startswith(b"enc1:") and b"secret" not in sealed
    assert cipher.open(sealed, "documents.data:a") == b"secret bytes"
    with pytest.raises(Exception):
        cipher.open(sealed, "documents.data:b")  # copied to another row
    text = cipher.seal_text('{"legal_name": "X"}', "applications.body:1")
    assert "legal_name" not in text
    assert cipher.open_text(text, "applications.body:1") == '{"legal_name": "X"}'


def test_cipher_without_key_is_plaintext_and_rejects_bad_keys():
    plain = Cipher()
    assert not plain.enabled
    assert plain.seal(b"enc1:looks sealed", "x") == b"enc1:looks sealed"
    assert plain.open(b"enc1:looks sealed", "x") == b"enc1:looks sealed"
    with pytest.raises(ValueError):
        Cipher(base64.b64encode(b"short").decode())


def _raw_database(directory):
    return Path(directory, "checker.sqlite3").read_bytes()


def test_store_encrypts_sensitive_columns_and_rotates(tmp_path):
    old = new_key()
    store = Store(tmp_path, Cipher(old))
    store.seed(ROOT / "samples/applications.json")
    application = store.application("APP-DEMO-001", "pvcb")
    documents = store.documents("APP-DEMO-001")
    assert application["legal_name"] and documents
    raw = _raw_database(tmp_path)
    assert application["legal_name"].encode() not in raw
    assert b"registration_number:" not in raw

    new = new_key()
    rotated = Store(tmp_path, Cipher(new, old))
    assert rotated.application("APP-DEMO-001", "pvcb") == application
    assert rotated.rotate() > 0
    assert rotated.rotate() == 0
    assert Store(tmp_path, Cipher(new)).documents("APP-DEMO-001") == documents
    with pytest.raises(Exception):
        Store(tmp_path, Cipher(old)).application("APP-DEMO-001", "pvcb")


def test_rotation_encrypts_legacy_plaintext_rows(tmp_path):
    Store(tmp_path).seed(ROOT / "samples/applications.json")
    name = Store(tmp_path).application("APP-DEMO-001", "pvcb")["legal_name"]
    assert name.encode() in _raw_database(tmp_path)
    store = Store(tmp_path, Cipher(new_key()))
    assert store.rotate() > 0
    assert store.application("APP-DEMO-001", "pvcb")["legal_name"] == name
    with sqlite3.connect(tmp_path / "checker.sqlite3") as db:
        db.execute("VACUUM")
    assert name.encode() not in _raw_database(tmp_path)


def test_encrypted_app_runs_check_and_serves_original(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_ENCRYPTION_KEY", new_key())
    client = TestClient(create_app(tmp_path, "demo"))
    result = client.post(
        "/api/applications/APP-DEMO-001/checks", json={"question": "Thiếu gì?"}, headers=CHECKER
    ).json()
    finding = next(f for f in result["findings"] if f.get("document_id"))
    evidence = client.get(f"/api/checks/{result['id']}/evidence/{finding['id']}", headers=CHECKER)
    assert evidence.status_code == 200
    original = client.get(evidence.json()["original_url"], headers=CHECKER)
    assert original.status_code == 200 and b":" in original.content
    raw = _raw_database(tmp_path)
    assert original.content not in raw
    assert result["application_snapshot"]["legal_name"].encode() not in raw


def test_production_requires_encryption_and_scanning(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("TOKENS_JSON", '{"' + "a" * 40 + '":{"user":"u","tenant":"pvcb","role":"checker"}}')
    with pytest.raises(ValueError, match="DATA_ENCRYPTION_KEY"):
        create_app(tmp_path, "demo")
    monkeypatch.setenv("DATA_ENCRYPTION_KEY", new_key())
    with pytest.raises(ValueError, match="MALWARE_SCAN"):
        create_app(tmp_path, "demo")
    monkeypatch.setenv("MALWARE_SCAN", "clamd")
    with pytest.raises(ValueError, match="BANK_MODE"):
        create_app(tmp_path, "demo")
    monkeypatch.setenv("BANK_MODE", "http")
    monkeypatch.setenv("BANK_API_URL", "https://bank.example")
    monkeypatch.setenv("BANK_API_TOKEN", "x" * 32)
    assert create_app(tmp_path, "demo")


# ---------------------------------------------------------------- malware scanning


class FakeClamd:
    """Speaks enough of the clamd INSTREAM protocol to test the client."""

    def __init__(self, reply=None):
        self.reply = reply
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen()
        self.port = self.sock.getsockname()[1]
        self.received = []
        threading.Thread(target=self.serve, daemon=True).start()

    def serve(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            with conn:
                command = b""
                while not command.endswith(b"\0"):
                    command += conn.recv(1)
                if command == b"zPING\0":
                    conn.sendall(b"PONG\0")
                    continue
                data = b""
                while True:
                    size = struct.unpack(">I", conn.recv(4, socket.MSG_WAITALL))[0]
                    if not size:
                        break
                    data += conn.recv(size, socket.MSG_WAITALL)
                self.received.append(data)
                if self.reply is not None:
                    conn.sendall(self.reply)
                elif b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE" in data:
                    conn.sendall(b"stream: Win.Test.EICAR_HDB-1 FOUND\0")
                else:
                    conn.sendall(b"stream: OK\0")

    def close(self):
        self.sock.close()


def test_clamd_client_verdicts():
    server = FakeClamd()
    scanner = ClamdScanner("127.0.0.1", server.port, timeout=5)
    assert scanner.ping()
    big = os.urandom(200_000)
    assert scanner.scan(big).clean and server.received[-1] == big
    verdict = scanner.scan(EICAR)
    assert not verdict.clean and verdict.signature == "Win.Test.EICAR_HDB-1"
    server.close()


def test_clamd_client_fails_closed():
    garbled = FakeClamd(b"INSTREAM size limit exceeded. ERROR\0")
    with pytest.raises(ScanUnavailable):
        ClamdScanner("127.0.0.1", garbled.port, timeout=5).scan(b"x")
    garbled.close()
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    with pytest.raises(ScanUnavailable):
        ClamdScanner("127.0.0.1", port, timeout=1).scan(b"x")


def _scanning_client(tmp_path, monkeypatch, port):
    monkeypatch.setenv("MALWARE_SCAN", "clamd")
    monkeypatch.setenv("CLAMD_PORT", str(port))
    monkeypatch.setenv("METRICS_TOKEN", "metrics-test-token")
    return TestClient(create_app(tmp_path, "demo"))


def _upload(client, data):
    return client.post(
        "/api/applications/APP-DEMO-001/documents",
        data={"kind": "business_license"},
        files={"file": ("license.txt", data)},
        headers=MAKER,
    )


def test_upload_is_scanned_before_storage(tmp_path, monkeypatch):
    server = FakeClamd()
    client = _scanning_client(tmp_path, monkeypatch, server.port)
    clean = _upload(client, b"legal_name: Test\n")
    assert clean.status_code == 201 and clean.json()["malware_scan"] == "clamd"
    infected = _upload(client, EICAR)
    assert infected.status_code == 422
    with client.app.state.store.db() as db:
        actions = [r["action"] for r in db.execute("SELECT action FROM audit")]
        stored = [bytes(r["data"]) for r in db.execute("SELECT data FROM documents")]
    assert "upload_rejected_malware" in actions
    assert EICAR not in stored
    metrics = client.get("/metrics", headers={"Authorization": "Bearer metrics-test-token"}).text
    assert 'mms_uploads_rejected_total{reason="malware"} 1' in metrics
    server.close()


def test_upload_rejected_when_scanner_down(tmp_path, monkeypatch):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    client = _scanning_client(tmp_path, monkeypatch, port)
    before = client.app.state.store.documents("APP-DEMO-001")
    assert _upload(client, b"legal_name: Test\n").status_code == 503
    assert client.app.state.store.documents("APP-DEMO-001") == before


@pytest.mark.skipif(not os.getenv("CLAMD_LIVE"), reason="set CLAMD_LIVE=host:port for real clamd")
def test_live_clamd_detects_eicar():
    host, port = os.environ["CLAMD_LIVE"].rsplit(":", 1)
    scanner = ClamdScanner(host, int(port), timeout=30)
    assert scanner.ping()
    assert scanner.scan(b"plain synthetic document").clean
    verdict = scanner.scan(EICAR)
    assert not verdict.clean and "Eicar" in verdict.signature


# ---------------------------------------------------------------- OIDC SSO


@pytest.fixture
def idp():
    server = MockIdP().start()
    yield server
    server.stop()


def _verifier(idp):
    return OIDCVerifier(
        idp.issuer, "mms-ai-checker", idp.jwks_url, ROLE_MAP, {"pvcb"}
    )


def test_oidc_maps_valid_token_to_server_principal(idp):
    verifier = _verifier(idp)
    assert verifier.principal(idp.token("checker1")) == {
        "user": "checker1", "tenant": "pvcb", "role": "checker"
    }
    assert verifier.principal(idp.token("maker1"))["role"] == "maker"


@pytest.mark.parametrize(
    "overrides, status",
    [
        ({"aud": "other-app"}, 401),
        ({"iss": "https://evil.example"}, 401),
        ({"exp": int(time.time()) - 3600}, 401),
        ({"nbf": int(time.time()) + 3600}, 401),
        ({"exp": None}, 401),
        ({"tenant": "other-bank"}, 403),
        ({"groups": []}, 403),
        ({"groups": ["mms-makers", "mms-checkers"]}, 403),
        ({"groups": ["mms-admins"]}, 403),
        ({"role": "checker", "groups": None}, 403),
    ],
)
def test_oidc_rejects_bad_claims(idp, overrides, status):
    from app.auth import AuthError

    with pytest.raises(AuthError) as error:
        _verifier(idp).principal(idp.token("checker1", **overrides))
    assert error.value.status == status


def test_oidc_rejects_forged_signatures(idp):
    from app.auth import AuthError

    verifier = _verifier(idp)
    claims = jwt.decode(idp.token("checker1"), options={"verify_signature": False})
    attacker = MockIdP()
    forged = jwt.encode(claims, attacker.key, algorithm="RS256", headers={"kid": idp.kid})
    unsigned = jwt.encode(claims, None, algorithm="none")
    # HMAC token with the provider's kid: refused by the algorithm allowlist before
    # any key lookup, so the public key can never be used as an HMAC secret.
    hmac_token = jwt.encode(
        claims, "shared-secret-value-that-is-long-enough", algorithm="HS256",
        headers={"kid": idp.kid},
    )
    for token in [forged, unsigned, hmac_token, "not-a-jwt"]:
        with pytest.raises(AuthError) as error:
            verifier.principal(token)
        assert error.value.status == 401


def test_oidc_config_validation(idp):
    with pytest.raises(ValueError):
        OIDCVerifier(idp.issuer, "aud", idp.jwks_url, ROLE_MAP, {"pvcb"}, algorithms=["HS256"])
    with pytest.raises(ValueError):
        OIDCVerifier(idp.issuer, "aud", "http://idp.example/jwks", ROLE_MAP, {"pvcb"})
    with pytest.raises(ValueError):
        OIDCVerifier(idp.issuer, "aud", idp.jwks_url, {"g": "admin"}, {"pvcb"})
    with pytest.raises(ValueError):
        OIDCVerifier(idp.issuer, "aud", idp.jwks_url, ROLE_MAP, set())


def test_api_with_oidc(tmp_path, monkeypatch, idp):
    for name, value in idp.env().items():
        monkeypatch.setenv(name, value)
    client = TestClient(create_app(tmp_path, "demo"))

    def bearer(user, **claims):
        return {"Authorization": f"Bearer {idp.token(user, **claims)}"}

    assert client.get("/api/applications", headers=CHECKER).status_code == 401
    assert client.get("/api/applications", headers=bearer("viewer1")).status_code == 200
    check = client.post(
        "/api/applications/APP-DEMO-001/checks", json={"question": "x"}, headers=bearer("viewer1")
    )
    assert check.status_code == 403
    check = client.post(
        "/api/applications/APP-DEMO-001/checks", json={"question": "x"}, headers=bearer("maker1")
    )
    assert check.status_code == 201
    other = client.get("/api/applications", headers=bearer("maker1", tenant="other-bank"))
    assert other.status_code == 403
    expired = client.get("/api/applications", headers=bearer("maker1", exp=1))
    assert expired.status_code == 401 and expired.headers["www-authenticate"] == "Bearer"
    with client.app.state.store.db() as db:
        actors = {r["actor"] for r in db.execute("SELECT actor FROM audit")}
    assert "maker1" in actors
    assert client.get("/healthz").json()["auth"] == "oidc"


def test_oidc_idp_down_returns_503(tmp_path, monkeypatch, idp):
    for name, value in idp.env().items():
        monkeypatch.setenv(name, value)
    client = TestClient(create_app(tmp_path, "demo"))
    token = idp.token("maker1")
    idp.stop()
    response = client.get("/api/applications", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 503


# ---------------------------------------------------------------- metrics


def test_metrics_disabled_without_token(tmp_path):
    client = TestClient(create_app(tmp_path, "demo"))
    assert client.get("/metrics").status_code == 404


def test_metrics_exposes_bounded_labels(tmp_path, monkeypatch):
    monkeypatch.setenv("METRICS_TOKEN", "metrics-test-token")
    client = TestClient(create_app(tmp_path, "demo"))
    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers=CHECKER).status_code == 401
    client.post(
        "/api/applications/APP-DEMO-001/checks", json={"question": "x"}, headers=CHECKER
    )
    client.get("/api/applications/APP-NOPE", headers=CHECKER)
    text = client.get("/metrics", headers={"Authorization": "Bearer metrics-test-token"}).text
    assert 'mms_checks_total{mode="demo"} 1' in text
    assert 'route="/api/applications/{app_id}/checks"' in text
    assert 'mms_findings_total{code="missing_document"}' in text
    assert "mms_http_request_seconds_bucket" in text
    for private in ["APP-DEMO-001", "APP-NOPE", "pvcb", "checker-demo"]:
        assert private not in text
