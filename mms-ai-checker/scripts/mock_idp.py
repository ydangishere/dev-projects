"""Local mock OpenID Connect identity provider for development and tests only.

Serves discovery and JWKS over HTTP on 127.0.0.1 and mints RS256 access tokens for
demo users. It has no login page and no client authentication: never expose it.

Run:  python scripts/mock_idp.py --port 9400
Then: AUTH_MODE=oidc OIDC_ISSUER=http://127.0.0.1:9400 OIDC_AUDIENCE=mms-ai-checker
      OIDC_JWKS_URL=http://127.0.0.1:9400/jwks OIDC_ALLOWED_TENANTS=pvcb
      OIDC_ROLE_MAP='{"mms-makers":"maker","mms-checkers":"checker","mms-viewers":"viewer"}'
The script prints one token per demo user to paste into the checker UI.
"""

from __future__ import annotations

import argparse
import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

AUDIENCE = "mms-ai-checker"
ROLE_MAP = {"mms-makers": "maker", "mms-checkers": "checker", "mms-viewers": "viewer"}
USERS = {
    "maker1": {"tenant": "pvcb", "groups": ["mms-makers"]},
    "checker1": {"tenant": "pvcb", "groups": ["mms-checkers"]},
    "viewer1": {"tenant": "pvcb", "groups": ["mms-viewers"]},
}


class MockIdP:
    def __init__(self, port: int = 0):
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.kid = uuid.uuid4().hex[:12]
        idp = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                if self.path == "/.well-known/openid-configuration":
                    body = {"issuer": idp.issuer, "jwks_uri": idp.jwks_url}
                elif self.path == "/jwks":
                    body = idp.jwks()
                else:
                    self.send_error(404)
                    return
                data = json.dumps(body).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.issuer = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.jwks_url = f"{self.issuer}/jwks"

    def jwks(self) -> dict:
        public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key()))
        return {"keys": [{**public, "kid": self.kid, "use": "sig", "alg": "RS256"}]}

    def token(self, user: str, ttl: int = 300, **overrides) -> str:
        now = int(time.time())
        claims = {
            "iss": self.issuer,
            "aud": AUDIENCE,
            "sub": f"sub-{user}",
            "preferred_username": user,
            "iat": now,
            "nbf": now,
            "exp": now + ttl,
            **USERS.get(user, {}),
        }
        claims.update(overrides)
        claims = {k: v for k, v in claims.items() if v is not None}
        return jwt.encode(claims, self.key, algorithm="RS256", headers={"kid": self.kid})

    def env(self) -> dict:
        return {
            "AUTH_MODE": "oidc",
            "OIDC_ISSUER": self.issuer,
            "OIDC_AUDIENCE": AUDIENCE,
            "OIDC_JWKS_URL": self.jwks_url,
            "OIDC_ALLOWED_TENANTS": "pvcb",
            "OIDC_ROLE_MAP": json.dumps(ROLE_MAP),
        }

    def start(self) -> "MockIdP":
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9400)
    parser.add_argument("--ttl", type=int, default=3600)
    args = parser.parse_args()
    idp = MockIdP(args.port).start()
    for name, value in idp.env().items():
        print(f"{name}={value}")
    for user in USERS:
        print(f"\n{user}: {idp.token(user, args.ttl)}")
    print("\nMock IdP running; Ctrl+C to stop.")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        idp.stop()
