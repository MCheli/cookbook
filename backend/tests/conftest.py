"""Tests run against a real Postgres (COOKBOOK_TEST_DATABASE_URL), rebuilt from the models."""

from __future__ import annotations

import os

os.environ.setdefault(
    "COOKBOOK_DATABASE_URL",
    os.environ.get(
        "COOKBOOK_TEST_DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5433/cookbook_test",
    ),
)
os.environ["COOKBOOK_DATABASE_URL"] = os.environ.get(
    "COOKBOOK_TEST_DATABASE_URL", os.environ["COOKBOOK_DATABASE_URL"]
)
os.environ["COOKBOOK_OWNER_EMAILS"] = "owner@test.local"
os.environ["COOKBOOK_TEST_USER_EMAIL"] = "owner@test.local"
os.environ["COOKBOOK_TEST_USER_PASSWORD"] = "owner-password"
os.environ.setdefault("COOKBOOK_JWT_SECRET", "test-secret-test-secret-test-secret-1234")
os.environ["COOKBOOK_GOOGLE_CLIENT_ID"] = ""
os.environ["COOKBOOK_GOOGLE_CLIENT_SECRET"] = ""

import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.config import settings  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import AsyncSessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.services.seed import run_startup_seed  # noqa: E402


@pytest.fixture(autouse=True)
async def fresh_db():
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.run_sync(Base.metadata.create_all)
    settings.DEMO_MODE = False
    await run_startup_seed()
    yield
    settings.DEMO_MODE = False


async def make_user(email: str, *, password: str | None = None) -> User:
    async with AsyncSessionLocal() as db:
        user = User(
            email=email,
            display_name=email.split("@")[0],
            preferences={},
            hashed_password=hash_password(password) if password else None,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


def client_for(user: User | None = None) -> httpx.AsyncClient:
    cookies = {"session": create_access_token(user.id)} if user else {}
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test", cookies=cookies
    )


async def get_user(email: str) -> User:
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        return await db.scalar(select(User).where(User.email == email))
