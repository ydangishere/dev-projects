"""Bank SSO through OpenID Connect access tokens (AUTH_MODE=oidc).

The app is an OIDC resource server: the bank identity provider signs a JWT, the
browser or gateway sends it as a Bearer token, and this module validates it locally
against the provider's published keys (JWKS). Validated claims are mapped to the same
server-side principal used by token mode: {user, tenant, role}.

Checks: signature (only the configured asymmetric algorithms, never `none` or HMAC),
issuer, audience, expiry, not-before, issued-at, subject. The tenant claim must be in
OIDC_ALLOWED_TENANTS. Identity-provider groups are mapped to exactly one app role
through OIDC_ROLE_MAP; a user mapped to several roles (for example maker and checker)
is refused, to keep maker-checker separation. No claim from the token can grant a
role or tenant that is not listed in server configuration.
"""

from __future__ import annotations

import json
import os
from urllib.parse import urlparse

import jwt

ROLES = {"maker", "checker", "viewer"}
ASYMMETRIC = {"RS256", "RS384", "RS512", "PS256", "PS384", "PS512", "ES256", "ES384"}


class AuthError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def _https_or_local(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" or (
        parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}
    )


class OIDCVerifier:
    def __init__(
        self,
        issuer: str,
        audience: str,
        jwks_url: str,
        role_map: dict[str, str],
        allowed_tenants: set[str],
        role_claim: str = "groups",
        tenant_claim: str = "tenant",
        user_claim: str = "preferred_username",
        algorithms: list[str] | None = None,
        leeway: int = 30,
        production: bool = False,
    ):
        algorithms = algorithms or ["RS256"]
        if not issuer or not audience or not jwks_url:
            raise ValueError("OIDC_ISSUER, OIDC_AUDIENCE and OIDC_JWKS_URL are required")
        if not set(algorithms) <= ASYMMETRIC:
            raise ValueError("OIDC_ALGORITHMS must be asymmetric (RS*/PS*/ES*)")
        if not role_map or not set(role_map.values()) <= ROLES:
            raise ValueError("OIDC_ROLE_MAP must map provider groups to maker/checker/viewer")
        if not allowed_tenants:
            raise ValueError("OIDC_ALLOWED_TENANTS is required")
        if not _https_or_local(jwks_url) or (production and not jwks_url.startswith("https://")):
            raise ValueError("OIDC_JWKS_URL must use HTTPS")
        self.issuer, self.audience = issuer, audience
        self.role_map, self.allowed_tenants = role_map, allowed_tenants
        self.role_claim, self.tenant_claim, self.user_claim = role_claim, tenant_claim, user_claim
        self.algorithms, self.leeway = algorithms, leeway
        self.jwks = jwt.PyJWKClient(jwks_url, cache_keys=True, lifespan=300, timeout=10)

    @classmethod
    def from_env(cls) -> "OIDCVerifier":
        return cls(
            issuer=os.getenv("OIDC_ISSUER", ""),
            audience=os.getenv("OIDC_AUDIENCE", ""),
            jwks_url=os.getenv("OIDC_JWKS_URL", ""),
            role_map=json.loads(os.getenv("OIDC_ROLE_MAP") or "{}"),
            allowed_tenants={
                t.strip() for t in os.getenv("OIDC_ALLOWED_TENANTS", "").split(",") if t.strip()
            },
            role_claim=os.getenv("OIDC_ROLE_CLAIM", "groups"),
            tenant_claim=os.getenv("OIDC_TENANT_CLAIM", "tenant"),
            user_claim=os.getenv("OIDC_USER_CLAIM", "preferred_username"),
            algorithms=[a.strip() for a in os.getenv("OIDC_ALGORITHMS", "RS256").split(",")],
            production=os.getenv("APP_ENV") == "production",
        )

    def principal(self, token: str) -> dict:
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") not in self.algorithms:
                raise AuthError(401, "Token algorithm not allowed")
            key = self.jwks.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                key,
                algorithms=self.algorithms,
                audience=self.audience,
                issuer=self.issuer,
                leeway=self.leeway,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
        except AuthError:
            raise
        except jwt.PyJWKClientConnectionError:
            raise AuthError(503, "Identity provider keys unavailable") from None
        except jwt.PyJWTError:
            raise AuthError(401, "Invalid or expired token") from None
        tenant = claims.get(self.tenant_claim)
        if not isinstance(tenant, str) or tenant not in self.allowed_tenants:
            raise AuthError(403, "Tenant not allowed")
        groups = claims.get(self.role_claim) or []
        if isinstance(groups, str):
            groups = [groups]
        roles = {self.role_map[g] for g in groups if isinstance(g, str) and g in self.role_map}
        if len(roles) != 1:
            raise AuthError(403, "Exactly one application role is required")
        user = claims.get(self.user_claim) or claims["sub"]
        if not isinstance(user, str) or not user or len(user) > 200:
            raise AuthError(401, "Invalid subject")
        return {"user": user, "tenant": tenant, "role": roles.pop()}
