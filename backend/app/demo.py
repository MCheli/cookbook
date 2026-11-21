"""Public demo mode (COOKBOOK_DEMO_MODE=true): cookbook-demo.markcheli.com.

Its own deployment and database, holding only the Claudius Banks seed (services/demo_seed.py),
rebuilt nightly. Anyone may look; nobody may change anything:

1. `DemoReadOnlyMiddleware` refuses every POST/PUT/PATCH/DELETE except `ALLOWED_WRITES`.
2. Request sessions run READ ONLY transactions, so a write that slips past still fails in Postgres.
3. Startup refuses Google/password settings and any database holding a non-persona user.

No AI calls happen in the demo: the persona has no Anthropic key, and the AI routes are writes.
"""

from __future__ import annotations

import re

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
DEMO_EMAIL_DOMAIN = "@cookbook.dev"
READ_ONLY_DETAIL = "This is the public demo with made-up data, so nothing can be changed or saved."

# Full paths. Everything else that writes is refused. The grocery preview is a pure calculation.
ALLOWED_WRITES = [
    re.compile(r"^/api/auth/(demo|logout)$"),
    re.compile(r"^/api/grocery/preview$"),
]


def write_allowed(method: str, path: str) -> bool:
    if method.upper() in SAFE_METHODS:
        return True
    return any(p.match(path) for p in ALLOWED_WRITES)


class DemoReadOnlyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if settings.DEMO_MODE and not write_allowed(request.method, request.url.path):
            return JSONResponse({"detail": READ_ONLY_DETAIL, "demo": True}, status_code=403)
        return await call_next(request)


class NoIndexMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if settings.DEMO_MODE:
            response.headers["X-Robots-Tag"] = "noindex, nofollow"
        return response


async def make_read_only(db: AsyncSession) -> None:
    await db.execute(text("SET TRANSACTION READ ONLY"))


def check_demo_settings() -> None:
    if settings.GOOGLE_CLIENT_ID or settings.GOOGLE_CLIENT_SECRET:
        raise RuntimeError(
            "FATAL: demo mode must not have Google SSO configured (COOKBOOK_GOOGLE_*)."
        )
    if settings.TEST_USER_EMAIL or settings.TEST_USER_PASSWORD:
        raise RuntimeError("FATAL: demo mode must not have a password user (COOKBOOK_TEST_USER_*).")
    if settings.OWNER_EMAILS:
        raise RuntimeError("FATAL: demo mode must not name real owners (COOKBOOK_OWNER_EMAILS).")
    if not settings.DEMO_USER_EMAIL.endswith(DEMO_EMAIL_DOMAIN):
        raise RuntimeError(
            f"FATAL: COOKBOOK_DEMO_USER_EMAIL must be a {DEMO_EMAIL_DOMAIN} persona."
        )


async def check_demo_database(db: AsyncSession) -> None:
    from app.models import User

    real = await db.scalar(select(User.id).where(~User.email.endswith(DEMO_EMAIL_DOMAIN)).limit(1))
    if real is not None:
        raise RuntimeError(
            "FATAL: demo mode is pointed at a database with real users. "
            "The demo must run on its own database holding only the seed."
        )
