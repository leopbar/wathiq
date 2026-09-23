"""Shared FastAPI dependencies: the current user and role gating."""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Annotated, Any
from uuid import UUID

import jwt
from fastapi import Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.db.enums import Role
from app.db.models import User
from app.db.session import get_db

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(auto_error=False, description="JWT from /auth/login")

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def _user_from_token(db: AsyncSession, raw_token: str) -> User:
    """The signed-in user, from whichever auth backend is configured.

    Both paths end at the same place — a `User` row with a `Role` — which is why no endpoint
    and no RBAC check had to change when Entra was added in M6.
    """
    if settings.entra_enabled:
        return await _user_from_entra_token(db, raw_token)

    try:
        payload = decode_access_token(raw_token)
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Your session expired — sign in again") from exc
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("Invalid session token") from exc

    user = await db.get(User, UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise UnauthorizedError("Account is not active")
    return user


async def _user_from_entra_token(db: AsyncSession, raw_token: str) -> User:
    """Validate a Microsoft Entra ID token and find, or create, the matching local user.

    Just-in-time provisioning: a person who has been granted a Wathiq app role in Entra can
    sign in without anybody creating an account here first. The local row is a cache of who
    they are, not the authority on it — so the role is rewritten from the token on every
    sign-in, and removing the app role in Entra takes their access away on the next request.

    The row carries an unusable password hash. These accounts have no local password, and
    storing something that `verify_password` could ever match would create a second way in
    that Entra knows nothing about.
    """
    from app.azure import entra

    try:
        claims = entra.validate_token(raw_token)
        role = entra.role_from_claims(claims)
        _subject, email, name = entra.identity_from_claims(claims)
    except entra.EntraAuthError as exc:
        raise UnauthorizedError(str(exc)) from exc

    user = (
        await db.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()

    if user is None:
        user = User(
            email=email,
            full_name=name,
            role=role,
            hashed_password="!entra",  # never matches a bcrypt hash, so it cannot be used
            is_active=True,
            is_demo=False,
        )
        db.add(user)
        await db.flush()
        logger.info("entra: provisioned %s as %s on first sign-in", email, role.value)
    elif user.role != role:
        logger.info(
            "entra: role for %s changed %s -> %s", email, user.role.value, role.value
        )
        user.role = role

    if not user.is_active:
        # Deactivating locally is a deliberate, immediate override — useful when Entra cannot
        # be changed quickly enough.
        raise UnauthorizedError("Account is not active")
    return user


async def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None:
        raise UnauthorizedError()
    return await _user_from_token(db, credentials.credentials)


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_user_browser(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    token: Annotated[str | None, Query(description="Token for browser-initiated GETs")] = None,
) -> User:
    """Auth for requests the browser makes itself.

    An `<iframe src>`, an `EventSource` and a download link cannot set an Authorization header,
    so these three GET endpoints also accept `?token=`. Deliberately narrow: tokens in URLs can
    end up in server logs and browser history, so no write endpoint accepts one. The production
    answer is short-lived signed URLs (see docs/DECISIONS.md).
    """
    if credentials is not None:
        return await _user_from_token(db, credentials.credentials)
    if token:
        return await _user_from_token(db, token)
    raise UnauthorizedError()


BrowserUser = Annotated[User, Depends(get_current_user_browser)]


def require_roles(*roles: Role) -> Callable[..., Coroutine[Any, Any, User]]:
    """Dependency factory: allow only these roles. Admin is never implicitly allowed."""

    allowed = set(roles)

    async def _guard(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise ForbiddenError(
                f"This action needs one of: {', '.join(sorted(r.value for r in allowed))}"
            )
        return user

    return _guard


# Frequently used role sets, named for readability at the call site.
ALL_ROLES = (Role.ops_officer, Role.reviewer, Role.supervisor, Role.admin, Role.auditor)
WRITE_ROLES = (Role.ops_officer, Role.supervisor, Role.admin)
REVIEW_ROLES = (Role.reviewer, Role.supervisor, Role.admin)
ADMIN_ONLY = (Role.admin,)


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None
