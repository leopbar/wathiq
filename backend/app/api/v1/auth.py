"""Sign-in endpoints.

Demo mode: local accounts, bcrypt hashes, JWT. Azure mode: Microsoft Entra ID (M6). The role
model is identical in both, so nothing downstream changes.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, status
from sqlalchemy import select

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession, client_ip
from app.core.errors import NotFoundError, UnauthorizedError
from app.core.security import create_access_token, verify_password
from app.db.models import User
from app.schemas.auth import (
    DemoLoginRequest,
    DemoUser,
    LoginRequest,
    TokenResponse,
    UserOut,
)
from app.services.demo_accounts import DEMO_ACCOUNTS
from app.services.events import record_user_event

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(
            user_id=user.id, email=user.email, role=user.role.value
        ),
        expires_in=settings.jwt_expire_minutes * 60,
        user=UserOut.model_validate(user),
    )


async def _load_active_user(db: DbSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email.lower().strip()))
    user = result.scalar_one_or_none()
    return user if user and user.is_active else None


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, request: Request, db: DbSession) -> TokenResponse:
    user = await _load_active_user(db, payload.email)
    # Verify even when the user is missing, so response time does not reveal valid emails.
    hashed = user.hashed_password if user else "$2b$12$" + "x" * 53
    if not verify_password(payload.password, hashed) or user is None:
        raise UnauthorizedError("Email or password is incorrect")

    await record_user_event(
        db,
        user=user,
        action="auth.login",
        label=f"{user.full_name} signed in",
        ip_address=client_ip(request),
    )
    await db.commit()
    return _token_response(user)


@router.get("/config")
async def auth_config() -> dict[str, object]:
    """What the sign-in screen needs to know, before anyone has signed in.

    Deliberately unauthenticated — the login page reads it to decide which sign-in methods to
    offer. It contains no secret: a tenant id and a client id are public identifiers that
    appear in the browser's address bar during any OIDC flow. The client *secret* is never
    here, and is never sent to a browser.
    """
    from app.azure import entra

    return {
        "backend": settings.auth_backend,
        "demo_accounts_available": settings.auth_backend == "demo",
        "entra": entra.describe(),
    }


@router.get("/demo-users", response_model=list[DemoUser])
async def demo_users() -> list[DemoUser]:
    """One-click sign-in cards. Empty unless local demo authentication is selected.

    Service mode and authentication are independent: the Azure-hosted demo deliberately uses
    real Azure providers with local accounts until an Entra browser app registration exists.
    """
    if settings.auth_backend != "demo":
        return []
    return [
        DemoUser(
            role=a.role,
            email=a.email,
            full_name=a.full_name,
            title=a.title,
            description=a.description,
        )
        for a in DEMO_ACCOUNTS
    ]


@router.post("/demo-login", response_model=TokenResponse)
async def demo_login(
    payload: DemoLoginRequest, request: Request, db: DbSession
) -> TokenResponse:
    if settings.auth_backend != "demo":
        raise NotFoundError("Demo sign-in")

    result = await db.execute(
        select(User).where(User.role == payload.role, User.is_demo.is_(True))
    )
    user = result.scalars().first()
    if user is None or not user.is_active:
        raise NotFoundError("Demo account")

    await record_user_event(
        db,
        user=user,
        action="auth.demo_login",
        label=f"{user.full_name} signed in with one-click demo access",
        detail={"role": user.role.value},
        ip_address=client_ip(request),
    )
    await db.commit()
    return _token_response(user)


@router.get("/me", response_model=UserOut, status_code=status.HTTP_200_OK)
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)
