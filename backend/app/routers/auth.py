"""Sign-in: Google (anyone with a verified Google account), the demo persona, dev password."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.oauth import is_google_configured, oauth_client
from app.core.rate_limit import login_limiter
from app.core.security import create_access_token, decode_session_token, verify_password
from app.db.session import get_db
from app.dependencies import (
    SESSION_COOKIE,
    clear_session_cookie,
    get_current_user,
    get_optional_user,
    is_owner,
    set_session_cookie,
)
from app.models import User
from app.schemas import LoginRequest, UserOut

logger = logging.getLogger("cookbook.auth")
router = APIRouter()


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_owner=is_owner(user),
        has_anthropic_key=bool(user.anthropic_key_enc),
        anthropic_key_last4=user.anthropic_key_last4,
        preferences=user.preferences or {},
    )


@router.get("/config")
async def auth_config() -> dict:
    return {
        "google_configured": is_google_configured(),
        "password_login": bool(settings.TEST_USER_EMAIL) and not is_google_configured(),
        "demo_mode": settings.DEMO_MODE,
        "demo_url": settings.DEMO_URL,
    }


@router.get("/session")
async def session_info(user: User | None = Depends(get_optional_user)) -> dict:
    """The signed-in user, or null: lets public pages ask without a 401."""
    return {"user": user_out(user).model_dump(mode="json") if user else None}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return user_out(user)


@router.post("/login", response_model=UserOut)
async def login(payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    """Local development only (COOKBOOK_TEST_USER_*). Hidden when Google is configured."""
    if settings.DEMO_MODE or not settings.TEST_USER_EMAIL:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    if login_limiter.is_blocked(payload.email):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many failed sign-ins.")
    user = await db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.hashed_password or ""):
        login_limiter.record_failure(payload.email)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    login_limiter.reset(payload.email)
    set_session_cookie(response, create_access_token(user.id))
    return user_out(user)


@router.post("/demo", response_model=UserOut)
async def demo_login(response: Response, db: AsyncSession = Depends(get_db)):
    if not settings.DEMO_MODE:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    user = await db.scalar(select(User).where(User.email == settings.DEMO_USER_EMAIL))
    if not user:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "The demo is being rebuilt. Try again in a minute."
        )
    set_session_cookie(response, create_access_token(user.id))
    return user_out(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    clear_session_cookie(response)


@router.get("/google/login")
async def google_login(request: Request, next: str | None = None):
    oauth = oauth_client()
    if oauth is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Google sign-in is not configured."
        )
    if next and next.startswith("/") and not next.startswith("//"):
        request.session["next"] = next
    redirect_uri = settings.GOOGLE_REDIRECT_URI or str(request.url_for("google_callback"))
    return await oauth.google.authorize_redirect(request, redirect_uri)


def _sign_in_failed(reason: str) -> RedirectResponse:
    # A JSON error is a dead end in an iPhone Home Screen web app: there is no back button.
    return RedirectResponse(url=f"/login?error={reason}", status_code=status.HTTP_302_FOUND)


@router.get("/google/callback", name="google_callback")
async def google_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """Anyone with a verified Google account may sign in. Each user's data is their own, and AI
    runs only on the user's own Anthropic key, so a new account can't spend anyone else's money."""
    oauth = oauth_client()
    if oauth is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Google sign-in is not configured."
        )
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as exc:  # noqa: BLE001 — Authlib raises various subclasses
        existing = request.cookies.get(SESSION_COOKIE)
        if existing and decode_session_token(existing):
            # iOS Home Screen apps can deliver the callback twice; the second copy fails state.
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        logger.warning("Google code exchange failed: %s: %s", type(exc).__name__, exc)
        return _sign_in_failed("google")

    userinfo = token.get("userinfo") or (await oauth.google.userinfo(token=token)) or {}
    sub, email = userinfo.get("sub"), userinfo.get("email")
    if not sub or not email:
        return _sign_in_failed("google")
    if userinfo.get("email_verified") not in (True, "true"):
        return _sign_in_failed("unverified")

    user = await db.scalar(select(User).where(User.google_sub == sub))
    if not user:
        user = await db.scalar(select(User).where(User.email == email.lower()))
    if user is None:
        user = User(
            email=email.lower(), google_sub=sub, display_name=userinfo.get("name"), preferences={}
        )
        db.add(user)
    else:
        user.google_sub = user.google_sub or sub
        if not user.display_name and userinfo.get("name"):
            user.display_name = userinfo["name"]
    await db.flush()

    next_path = request.session.pop("next", None) or "/"
    redirect = RedirectResponse(url=next_path, status_code=status.HTTP_302_FOUND)
    set_session_cookie(redirect, create_access_token(user.id))
    return redirect
