"""Shared FastAPI dependencies: the current user and role gating."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Annotated, Any
from uuid import UUID

import jwt
from fastapi import Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.db.enums import Role
from app.db.models import User
from app.db.session import get_db

bearer_scheme = HTTPBearer(auto_error=False, description="JWT from /auth/login")

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def _user_from_token(db: AsyncSession, raw_token: str) -> User:
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
