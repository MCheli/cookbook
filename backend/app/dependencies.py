"""Request dependencies: the signed-in user (cookie or X-API-Key), optional for public pages."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Cookie, Depends, Header, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import decode_session_token, refreshed_access_token
from app.db.session import get_db
from app.models import ApiKey, User

SESSION_COOKIE = "session"
API_KEY_HEADER = "X-API-Key"


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=settings.JWT_EXPIRE_DAYS * 24 * 60 * 60,
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE, domain=settings.COOKIE_DOMAIN, path="/")


def is_owner(user: User | None) -> bool:
    return bool(user) and user.email.lower() in settings.owner_emails


async def _resolve(
    response: Response, session: str | None, x_api_key: str | None, db: AsyncSession
) -> User | None:
    if x_api_key:
        return await _user_from_api_key(db, x_api_key)
    if not session:
        return None
    token = decode_session_token(session)
    if not token:
        return None
    user = await db.scalar(select(User).where(User.id == token.user_id))
    if user:
        renewed = refreshed_access_token(token)
        if renewed:
            set_session_cookie(response, renewed)
    return user


async def get_optional_user(
    response: Response,
    session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    x_api_key: str | None = Header(default=None, alias=API_KEY_HEADER),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Public pages: the visitor if signed in, else None. A bad API key is still a 401."""
    return await _resolve(response, session, x_api_key, db)


async def get_current_user(
    response: Response,
    session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    x_api_key: str | None = Header(default=None, alias=API_KEY_HEADER),
    db: AsyncSession = Depends(get_db),
) -> User:
    user = await _resolve(response, session, x_api_key, db)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    return user


async def _user_from_api_key(db: AsyncSession, raw: str) -> User:
    if not raw.startswith(ApiKey.KEY_PREFIX):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")
    record = await db.scalar(
        select(ApiKey).where(ApiKey.key_hash == ApiKey.hash_key(raw), ApiKey.is_active.is_(True))
    )
    user = await db.scalar(select(User).where(User.id == record.user_id)) if record else None
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")
    if not settings.DEMO_MODE:  # the demo's sessions are read-only
        record.last_used_at = datetime.now(UTC)
    return user
