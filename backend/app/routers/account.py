"""The signed-in user's settings: Anthropic key (BYOK), food profile, API keys, AI usage."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.pricing import estimate_cost_usd
from app.core.crypto import encrypt_secret
from app.db.session import get_db
from app.dependencies import get_current_user
from app.models import AiUsage, ApiKey, User
from app.routers.auth import user_out
from app.schemas import (
    AnthropicKeyIn,
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyOut,
    PreferencesIn,
    UserOut,
)

router = APIRouter()


def _check_key_with_anthropic(key: str) -> None:
    """One cheap authenticated call, so a typo is caught when it's pasted, not mid-recipe."""
    try:
        anthropic.Anthropic(api_key=key, timeout=15, max_retries=1).models.list(limit=1)
    except anthropic.AuthenticationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Anthropic rejected that key.") from exc
    except anthropic.PermissionDeniedError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "That key isn't allowed to use the API."
        ) from exc
    except anthropic.APIConnectionError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "Couldn't reach Anthropic to check the key."
        ) from exc


@router.put("/anthropic-key", response_model=UserOut)
async def set_anthropic_key(
    payload: AnthropicKeyIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    key = payload.key.strip()
    if not key.startswith("sk-ant-"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Anthropic API keys start with sk-ant-.")
    _check_key_with_anthropic(key)
    user.anthropic_key_enc = encrypt_secret(key)
    user.anthropic_key_last4 = key[-4:]
    await db.flush()
    return user_out(user)


@router.delete("/anthropic-key", response_model=UserOut)
async def delete_anthropic_key(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    user.anthropic_key_enc = None
    user.anthropic_key_last4 = None
    await db.flush()
    return user_out(user)


@router.put("/preferences", response_model=UserOut)
async def set_preferences(
    payload: PreferencesIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user.preferences = {k: v for k, v in payload.model_dump().items() if v not in (None, "")}
    await db.flush()
    return user_out(user)


@router.get("/usage")
async def ai_usage(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    """This month's AI use on the user's own key (an estimate; Anthropic's console is the bill)."""
    start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    rows = (
        await db.execute(
            select(
                AiUsage.model,
                func.count(),
                func.sum(AiUsage.input_tokens),
                func.sum(AiUsage.output_tokens),
            )
            .where(AiUsage.user_id == user.id, AiUsage.created_at >= start)
            .group_by(AiUsage.model)
        )
    ).all()
    models = [
        {
            "model": model,
            "calls": calls,
            "input_tokens": int(inp or 0),
            "output_tokens": int(out or 0),
            "estimated_usd": round(estimate_cost_usd(model, int(inp or 0), int(out or 0)), 4),
        }
        for model, calls, inp, out in rows
    ]
    return {
        "since": start.date().isoformat(),
        "models": models,
        "estimated_usd": round(sum(m["estimated_usd"] for m in models), 4),
    }


@router.get("/api-keys", response_model=list[ApiKeyOut])
async def list_api_keys(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(
        select(ApiKey).where(ApiKey.user_id == user.id).order_by(ApiKey.created_at.desc())
    )
    return list(rows)


@router.post("/api-keys", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: ApiKeyCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    raw = ApiKey.generate_key()
    record = ApiKey(
        user_id=user.id,
        name=payload.name.strip(),
        key_prefix=raw[:12],
        key_hash=ApiKey.hash_key(raw),
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return ApiKeyCreated(**ApiKeyOut.model_validate(record).model_dump(), key=raw)


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> None:
    record = await db.scalar(select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id))
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "API key not found")
    await db.delete(record)
