"""Verifies Clerk session tokens for hosted sign-in (Task 19.4, M19).

Only used when `DEAL_LAB_AUTH_MODE=clerk`. Local development keeps the
dev identity switcher (surface #5 stub) and never touches this module.

A Clerk session token is an RS256-signed JWT, sent as the `__session` cookie
on same-origin requests (this app serves its React build from the same
origin as its API) or as `Authorization: Bearer`. Following Clerk's manual
verification guide, this checks the signature against the instance's JWKS,
the algorithm, `exp`/`nbf`, the issuer, and - when present - that `azp`
(the origin that minted the token) is one of this deployment's origins.

The token proves who someone is; whether they may use this workspace is
decided by `identity` (invite-only: an existing local user, linked by Clerk
user id or, on first sign-in, by the `email` custom claim).

Configuration: `DEAL_LAB_AUTH_JWKS_URL` (the Clerk Frontend API URL +
`/.well-known/jwks.json`), `DEAL_LAB_AUTH_ISSUER` (the Frontend API URL),
`DEAL_LAB_AUTH_AUTHORIZED_PARTIES` (comma-separated origins, e.g.
`https://staging.example.com`).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import jwt

LEEWAY_SECONDS = 5


class TokenError(Exception):
    """The token is missing, malformed, expired, or not from this deployment."""


@dataclass
class VerifiedToken:
    subject: str  # Clerk user id
    email: str | None  # from the `email` custom claim, if configured


_jwks_client: Any = None


def _signing_key(token: str) -> Any:
    global _jwks_client
    if _jwks_client is None:
        url = os.environ.get("DEAL_LAB_AUTH_JWKS_URL", "").strip()
        if not url:
            raise TokenError("sign-in is not configured (DEAL_LAB_AUTH_JWKS_URL)")
        _jwks_client = jwt.PyJWKClient(url, cache_keys=True)
    return _jwks_client.get_signing_key_from_jwt(token).key


def set_key_resolver(resolver: Any) -> None:
    """Tests only: replace JWKS lookup with an object exposing
    get_signing_key_from_jwt(token).key (or None to reset)."""
    global _jwks_client
    _jwks_client = resolver


def verify(token: str) -> VerifiedToken:
    issuer = os.environ.get("DEAL_LAB_AUTH_ISSUER", "").strip()
    if not issuer:
        raise TokenError("sign-in is not configured (DEAL_LAB_AUTH_ISSUER)")
    try:
        claims = jwt.decode(
            token,
            _signing_key(token),
            algorithms=["RS256"],
            issuer=issuer,
            leeway=LEEWAY_SECONDS,
            options={"require": ["exp", "iat", "sub", "iss"], "verify_aud": False},
        )
    except TokenError:
        raise
    except Exception as exc:
        raise TokenError(f"invalid session token: {type(exc).__name__}") from exc

    allowed = {o.strip() for o in os.environ.get("DEAL_LAB_AUTH_AUTHORIZED_PARTIES", "").split(",") if o.strip()}
    azp = claims.get("azp")
    if azp is not None and allowed and azp not in allowed:
        raise TokenError("session token was issued for a different origin")

    email = claims.get("email")
    return VerifiedToken(subject=str(claims["sub"]), email=str(email).strip().lower() if email else None)
