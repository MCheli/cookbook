"""Async SQLAlchemy session management."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)

AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncIterator[AsyncSession]:
    """Yield a session that commits on success. Demo requests run READ ONLY (app/demo.py)."""
    async with AsyncSessionLocal() as session:
        try:
            if settings.DEMO_MODE:
                from app.demo import make_read_only

                await make_read_only(session)
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
