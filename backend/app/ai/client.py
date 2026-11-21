"""The one place the cookbook talks to Claude, always on the signed-in user's own key.

- `parse(...)` returns a validated Pydantic instance (structured outputs).
- `create(...)` is one conversational turn, optionally with tools (the chat).
Every call is logged (model, purpose, tokens) to ai_usage for the user's Settings page, and every
failure becomes an AIError with a message the UI can show.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, TypeVar

import anthropic
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.crypto import decrypt_secret
from app.models import AiUsage, User

logger = logging.getLogger("cookbook.ai")
T = TypeVar("T", bound=BaseModel)
TIMEOUT_SECONDS = 120.0


class AIError(Exception):
    def __init__(self, message: str, *, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


class NoKeyError(AIError):
    def __init__(self):
        super().__init__(
            "AI features use your own Anthropic API key. Add one in Settings.", status_code=402
        )


# Tests swap this for a fake. Signature: factory(api_key) -> client with .messages.
def _default_factory(api_key: str) -> Any:
    return anthropic.Anthropic(api_key=api_key, timeout=TIMEOUT_SECONDS, max_retries=2)


client_factory = _default_factory


def user_client(user: User) -> Any:
    if settings.DEMO_MODE or not user.anthropic_key_enc:
        raise NoKeyError()
    key = decrypt_secret(user.anthropic_key_enc)
    if not key:
        raise AIError(
            "Your saved Anthropic key can't be read any more. Add it again in Settings.",
            status_code=402,
        )
    return client_factory(key)


def model_for(tier: str) -> str:
    return settings.AI_MODEL_SMART if tier == "smart" else settings.AI_MODEL


def _translate(exc: Exception) -> AIError:
    if isinstance(exc, AIError):
        return exc
    if isinstance(exc, anthropic.AuthenticationError):
        return AIError("Anthropic rejected your API key. Check it in Settings.", status_code=402)
    if isinstance(exc, anthropic.PermissionDeniedError):
        return AIError(
            "Your Anthropic key isn't allowed to do that (check its workspace limits).",
            status_code=402,
        )
    if isinstance(exc, anthropic.RateLimitError):
        return AIError(
            "Anthropic's rate limit for your key was reached; try again in a minute.",
            status_code=429,
        )
    if isinstance(exc, anthropic.BadRequestError):
        msg = getattr(exc, "message", str(exc))
        if "credit" in msg.lower() or "billing" in msg.lower():
            return AIError("Your Anthropic account is out of credit.", status_code=402)
        return AIError(f"Anthropic rejected the request: {msg}", status_code=502)
    if isinstance(exc, anthropic.APIStatusError):
        return AIError(f"Anthropic error {exc.status_code}; try again.", status_code=502)
    if isinstance(exc, anthropic.APIConnectionError):
        return AIError("Couldn't reach Anthropic.", status_code=502)
    return AIError(f"AI call failed: {type(exc).__name__}", status_code=502)


async def _record(
    db: AsyncSession, user: User, purpose: str, model: str, response: Any, started: float
) -> None:
    usage = getattr(response, "usage", None)
    inp = int(getattr(usage, "input_tokens", 0) or 0)
    out = int(getattr(usage, "output_tokens", 0) or 0)
    logger.info(
        "ai purpose=%s model=%s in=%s out=%s stop=%s ms=%d",
        purpose,
        model,
        inp,
        out,
        getattr(response, "stop_reason", None),
        int((time.monotonic() - started) * 1000),
    )
    db.add(
        AiUsage(user_id=user.id, purpose=purpose, model=model, input_tokens=inp, output_tokens=out)
    )
    await db.flush()


def _check_stop(response: Any, purpose: str) -> None:
    stop = getattr(response, "stop_reason", None)
    if stop == "refusal":
        raise AIError(f"Claude declined the {purpose} request.", status_code=422)
    if stop == "max_tokens":
        raise AIError(f"The {purpose} answer was cut off; try a shorter request.", status_code=502)


async def parse(
    db: AsyncSession,
    user: User,
    schema: type[T],
    *,
    system: str,
    content: str | list[dict[str, Any]],
    purpose: str,
    tier: str = "fast",
    max_tokens: int = 8000,
) -> T:
    client = user_client(user)
    model = model_for(tier)
    started = time.monotonic()
    try:
        response = await asyncio.to_thread(
            client.messages.parse,
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": content}],
            output_format=schema,
        )
    except Exception as exc:  # translated, never swallowed
        err = _translate(exc)
        logger.warning("ai purpose=%s model=%s failed: %s", purpose, model, err)
        raise err from exc
    await _record(db, user, purpose, model, response, started)
    _check_stop(response, purpose)
    parsed = getattr(response, "parsed_output", None)
    if parsed is None:
        raise AIError(f"Claude returned no structured {purpose} answer.", status_code=502)
    return parsed


async def create(
    db: AsyncSession,
    user: User,
    *,
    system: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    purpose: str = "chat",
    tier: str = "fast",
    max_tokens: int = 4000,
) -> Any:
    client = user_client(user)
    model = model_for(tier)
    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": messages,
    }
    if tools:
        kwargs["tools"] = tools
    started = time.monotonic()
    try:
        response = await asyncio.to_thread(client.messages.create, **kwargs)
    except Exception as exc:
        err = _translate(exc)
        logger.warning("ai purpose=%s model=%s failed: %s", purpose, model, err)
        raise err from exc
    await _record(db, user, purpose, model, response, started)
    if getattr(response, "stop_reason", None) == "refusal":
        raise AIError("Claude declined that request.", status_code=422)
    return response
