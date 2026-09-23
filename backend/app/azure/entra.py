"""Microsoft Entra ID: signing in with a work account.

The demo backend issues its own JWT to a local account. This one validates a JWT that Entra
issued, against Entra's public keys. Everything downstream is unchanged: `get_current_user`
still ends up with a `User` row and a `Role`, and every RBAC check in the API still reads that
role. Only where the token came from changes. `WATHIQ_AUTH_BACKEND=entra` switches it.

**Validation is the whole job, and it is done properly.** A token is accepted only if all of
the following hold, and each one is a real attack if it is skipped:

* the signature matches a key currently published at the tenant's JWKS endpoint — and the key
  is chosen by the token's own `kid`, fetched over HTTPS, never hard-coded;
* the algorithm is RS256. PyJWT is told the allowed list explicitly, because the classic JWT
  attack is a token that asks to be verified with `none`, or with `HS256` using the public key
  as an HMAC secret;
* `aud` is this application's client id — a token minted for a *different* app in the same
  tenant is a valid token, and it is not valid *here*;
* `iss` is this tenant's v2 issuer, so an account from another tenant cannot sign in;
* `exp` and `nbf` are present and current.

**Roles come from the token, never from the database.** Entra is the authority on who a person
is and what they may do, so an app role in the token wins over whatever a local row happens to
say. A user signing in for the first time is created on the spot (just-in-time provisioning)
with the role the token carries; on later sign-ins the local row is updated to match. That
keeps "remove the app role in Entra" working as a way to take access away, which is the reason
a bank wants Entra in front of this at all. (DECISIONS #73)

A token with no recognised app role is rejected. It is not given the lowest role: silently
downgrading an unknown role would turn a misconfigured app registration into a person quietly
holding permissions nobody granted.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import jwt

from app.core.config import settings
from app.db.enums import Role

logger = logging.getLogger(__name__)

ALGORITHMS = ["RS256"]

# Entra app roles, as configured on the app registration, mapped to Wathiq's five roles. The
# names on the left are what an administrator types into the Azure portal; keeping them
# explicit here means a typo in the portal fails closed rather than granting something.
# The order is least to most privileged, and `role_from_claims` relies on it when a token
# carries more than one. Auditor sits low deliberately: it is a read-everything, change-nothing
# role, so it grants less power than a reviewer who can approve a case.
ROLE_MAP: dict[str, Role] = {
    "Wathiq.OpsOfficer": Role.ops_officer,
    "Wathiq.Auditor": Role.auditor,
    "Wathiq.Reviewer": Role.reviewer,
    "Wathiq.Supervisor": Role.supervisor,
    "Wathiq.Admin": Role.admin,
}


class EntraAuthError(Exception):
    """A token that cannot be accepted. The message is safe to show a user."""


def issuer() -> str:
    return f"https://login.microsoftonline.com/{settings.entra_tenant_id.strip()}/v2.0"


def jwks_uri() -> str:
    return (
        f"https://login.microsoftonline.com/{settings.entra_tenant_id.strip()}"
        "/discovery/v2.0/keys"
    )


def authority() -> str:
    """What the browser is sent to in order to sign in."""
    return f"https://login.microsoftonline.com/{settings.entra_tenant_id.strip()}"


@lru_cache(maxsize=1)
def _jwk_client() -> Any:
    """A cached JWKS client.

    Cached because it holds the fetched signing keys: asking Entra for the key set on every
    request would add a round trip to every API call and would be rate-limited soon enough.
    PyJWT refreshes the set by itself when a token arrives with a `kid` it has not seen, which
    is what makes key rotation work without a restart.
    """
    return jwt.PyJWKClient(jwks_uri(), cache_keys=True)


def reset_keys() -> None:
    """Drop the cached JWKS client — for tests, and after a tenant id change."""
    _jwk_client.cache_clear()


def validate_token(raw_token: str) -> dict[str, Any]:
    """Verify an Entra access token and return its claims, or raise `EntraAuthError`."""
    tenant = settings.entra_tenant_id.strip()
    client_id = settings.entra_client_id.strip()
    if not tenant or not client_id:
        raise EntraAuthError("Entra sign-in is not configured")

    try:
        signing_key = _jwk_client().get_signing_key_from_jwt(raw_token)
        return jwt.decode(
            raw_token,
            signing_key.key,
            algorithms=ALGORITHMS,
            audience=client_id,
            issuer=issuer(),
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise EntraAuthError("Your session expired — sign in again") from exc
    except jwt.InvalidAudienceError as exc:
        raise EntraAuthError("This token was issued for a different application") from exc
    except jwt.InvalidIssuerError as exc:
        raise EntraAuthError("This token was issued by a different tenant") from exc
    except jwt.PyJWTError as exc:
        # Everything else — a bad signature, a missing claim, an unknown key — is one message.
        # Telling a caller *which* check failed is free reconnaissance for an attacker.
        logger.warning("entra: rejected a token: %s", exc)
        raise EntraAuthError("Invalid sign-in token") from exc


def role_from_claims(claims: dict[str, Any]) -> Role:
    """The Wathiq role this token grants, or raise if it grants none.

    When a token carries several app roles — a supervisor who is also an auditor — the most
    privileged one wins, which is the ordering `ROLE_MAP` is written in.
    """
    granted = claims.get("roles") or []
    if isinstance(granted, str):
        granted = [granted]

    matched = [ROLE_MAP[name] for name in granted if name in ROLE_MAP]
    if not matched:
        raise EntraAuthError(
            "Your account has no Wathiq role assigned. Ask an administrator to grant one of: "
            + ", ".join(ROLE_MAP)
        )
    order = list(ROLE_MAP.values())
    return max(matched, key=order.index)


def identity_from_claims(claims: dict[str, Any]) -> tuple[str, str, str]:
    """`(subject, email, display name)` from the claims, with sensible fallbacks.

    `oid` is preferred over `sub`: it is the user's stable object id in the tenant, whereas
    `sub` is only stable per application. Two Wathiq app registrations would see different
    `sub` values for the same person.
    """
    subject = str(claims.get("oid") or claims.get("sub") or "").strip()
    email = str(
        claims.get("preferred_username") or claims.get("email") or claims.get("upn") or ""
    ).strip().lower()
    name = str(claims.get("name") or email or subject).strip()
    if not subject or not email:
        raise EntraAuthError("This token does not identify a user")
    return subject, email, name


def describe() -> dict[str, Any]:
    """What the login screen needs to offer 'Sign in with Microsoft'. No secrets."""
    return {
        "enabled": settings.entra_enabled,
        "authority": authority() if settings.entra_enabled else "",
        "client_id": settings.entra_client_id if settings.entra_enabled else "",
        "tenant_id": settings.entra_tenant_id if settings.entra_enabled else "",
        "scopes": [f"api://{settings.entra_client_id}/access_as_user"]
        if settings.entra_enabled
        else [],
        "roles": list(ROLE_MAP),
    }


__all__ = [
    "ALGORITHMS",
    "ROLE_MAP",
    "EntraAuthError",
    "authority",
    "describe",
    "identity_from_claims",
    "issuer",
    "jwks_uri",
    "reset_keys",
    "role_from_claims",
    "validate_token",
]
