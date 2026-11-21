"""AI features, on the signed-in user's own Anthropic key. Nothing AI writes is published unreviewed:
drafts are private, adapted versions come back for the cook to keep or throw away."""

from __future__ import annotations

import base64
import json
from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import client as ai
from app.ai.prompts import CHAT_TASK, recipe_system
from app.ai.schemas import AdaptResult, Ideas, ProductMatches, RecipeDraft, WeekPlan
from app.ai.tools import TOOLS, run_tool
from app.db.session import get_db
from app.dependencies import get_current_user
from app.models import ChatMessage, ChatThread, CookLog, Product, Recipe, ShoppingList, User
from app.services import lists as lists_svc
from app.services import recipes as recipes_svc
from app.services import web_import

router = APIRouter()
MAX_TOOL_ROUNDS = 6
MAX_IMAGE_BYTES = 5_000_000


def _raise(exc: ai.AIError):
    raise HTTPException(exc.status_code, str(exc)) from exc


class PromptIn(BaseModel):
    prompt: str = Field(min_length=2, max_length=3000)


class AdaptIn(BaseModel):
    instruction: str = Field(min_length=2, max_length=2000)


class UrlIn(BaseModel):
    url: str = Field(min_length=8, max_length=2000)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    thread_id: UUID | None = None
    recipe_slug: str | None = None


@router.get("/status")
async def ai_status(user: User = Depends(get_current_user)) -> dict:
    return {
        "available": bool(user.anthropic_key_enc),
        "reason": None if user.anthropic_key_enc else "no_key",
    }


@router.post("/recipes/{recipe_id}/adapt")
async def adapt_recipe(
    recipe_id: UUID,
    payload: AdaptIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """'I'm missing heavy cream', 'make it spicier', 'Instant Pot version', 'serves 2'.
    Returns a changed version; nothing is saved until the cook keeps it."""
    recipe = await recipes_svc.get_visible(db, str(recipe_id), user)
    system = recipe_system(
        user,
        (
            "Rewrite the recipe below to satisfy the cook's request. Change only what the request needs; "
            "keep the rest (wording, groups, amounts) as written. Keep the house format. "
            "List every change in change_summary."
        ),
    )
    content = f"Recipe:\n\n{recipes_svc.recipe_markdown(recipe)}\n\nRequest: {payload.instruction}"
    try:
        result = await ai.parse(
            db, user, AdaptResult, system=system, content=content, purpose="adapt"
        )
    except ai.AIError as exc:
        _raise(exc)
    return {
        "recipe": result.recipe.model_dump(),
        "change_summary": result.change_summary,
        "variant_name": result.variant_name,
        "based_on": {"id": str(recipe.id), "slug": recipe.slug, "title": recipe.title},
        "ai_meta": {"model": ai.model_for("fast"), "prompt": payload.instruction},
    }


@router.post("/ideas")
async def brainstorm(
    payload: PromptIn, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    titles = list(await db.scalars(select(Recipe.slug).where(recipes_svc.visible_clause(user))))
    system = recipe_system(
        user,
        (
            "Brainstorm 5 recipe ideas for the cook's request. Prefer variety in method and protein. "
            "If a recipe already in the cookbook fits, include it with existing_slug set.\n"
            f"Cookbook slugs: {', '.join(titles)}"
        ),
    )
    try:
        result = await ai.parse(
            db, user, Ideas, system=system, content=payload.prompt, purpose="ideas"
        )
    except ai.AIError as exc:
        _raise(exc)
    return result.model_dump()


@router.post("/generate")
async def generate_recipe(
    payload: PromptIn, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    """A full recipe from a prompt or a picked idea. Returned for review, not saved."""
    system = recipe_system(
        user, "Write one complete recipe for the cook's request in the house format."
    )
    try:
        draft = await ai.parse(
            db,
            user,
            RecipeDraft,
            system=system,
            content=payload.prompt,
            purpose="generate",
            tier="smart",
        )
    except ai.AIError as exc:
        _raise(exc)
    return {
        "recipe": draft.model_dump(),
        "ai_meta": {"model": ai.model_for("smart"), "prompt": payload.prompt},
    }


@router.post("/import-url")
async def import_url(
    payload: UrlIn, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    """schema.org JSON-LD when the page has it (no AI, no key needed); otherwise Claude reads it."""
    try:
        html = await web_import.fetch_page(payload.url)
    except web_import.ImportError_ as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — network trouble of any kind
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Couldn't load that page.") from exc
    node = web_import.find_jsonld_recipe(html)
    if node:
        return {"recipe": web_import.jsonld_to_payload(node, payload.url), "via": "jsonld"}
    system = recipe_system(
        user,
        (
            "Extract the recipe from this web page text into the house format. Keep the author's "
            "ingredients and amounts; rewrite steps concisely with bold labels. If there is no recipe, "
            "return a recipe titled 'No recipe found' with no ingredients."
        ),
    )
    try:
        draft = await ai.parse(
            db,
            user,
            RecipeDraft,
            system=system,
            content=web_import.page_text(html),
            purpose="import_url",
        )
    except ai.AIError as exc:
        _raise(exc)
    if not draft.ingredients:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "No recipe found on that page.")
    data = draft.model_dump()
    data.update({"source": "import", "source_url": payload.url})
    return {"recipe": data, "via": "ai"}


@router.post("/import-photo")
async def import_photo(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """A photo of a cookbook page or recipe card."""
    media = (file.content_type or "").lower()
    if media not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Use a JPEG, PNG or WebP photo.")
    data = await file.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Photos up to 5 MB, please.")
    system = recipe_system(
        user, "Transcribe the recipe in this photo into the house format. Keep its amounts."
    )
    content = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media,
                "data": base64.b64encode(data).decode(),
            },
        },
        {"type": "text", "text": "Here is the recipe."},
    ]
    try:
        draft = await ai.parse(
            db, user, RecipeDraft, system=system, content=content, purpose="import_photo"
        )
    except ai.AIError as exc:
        _raise(exc)
    out = draft.model_dump()
    out["source"] = "import"
    return {"recipe": out, "via": "ai"}


@router.post("/suggest-week")
async def suggest_week(
    payload: PromptIn | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    recipes = list(
        await db.scalars(
            select(Recipe).where(recipes_svc.visible_clause(user), Recipe.status == "published")
        )
    )
    since = date.today() - timedelta(days=42)
    cooked = (
        await db.execute(
            select(CookLog.cooked_on, Recipe.slug, CookLog.rating)
            .join(Recipe, Recipe.id == CookLog.recipe_id)
            .where(CookLog.user_id == user.id, CookLog.cooked_on >= since)
            .order_by(CookLog.cooked_on.desc())
        )
    ).all()
    recent_lists = list(
        await db.scalars(
            select(ShoppingList)
            .where(ShoppingList.user_id == user.id, ShoppingList.status == "ordered")
            .order_by(ShoppingList.ordered_at.desc())
            .limit(3)
        )
    )
    recent_ids = {r.recipe_id for lst in recent_lists for r in lst.recipes}
    catalog = "\n".join(f"- {r.slug}: {r.title} ({r.method}; {', '.join(r.tags)})" for r in recipes)
    history = "\n".join(f"- {d}: {s} (rating {rt or '-'})" for d, s, rt in cooked) or "none logged"
    recent = ", ".join(r.slug for r in recipes if r.id in recent_ids) or "none"
    system = recipe_system(
        user,
        (
            "Pick 2 recipes from the cookbook for this week (or as many as the cook asks for), avoiding "
            "anything ordered in the last two weeks, and mixing methods and proteins. Then suggest one new "
            "idea not in the cookbook. Use exact slugs.\n\n"
            f"Cookbook:\n{catalog}\n\nCooked in the last 6 weeks:\n{history}\n\nOn recent orders: {recent}"
        ),
    )
    try:
        plan = await ai.parse(
            db,
            user,
            WeekPlan,
            system=system,
            content=(payload.prompt if payload else "Plan this week."),
            purpose="suggest_week",
        )
    except ai.AIError as exc:
        _raise(exc)
    by_slug = {r.slug: r for r in recipes}
    picks = [
        {
            "slug": p.slug,
            "title": by_slug[p.slug].title,
            "emoji": by_slug[p.slug].emoji,
            "id": str(by_slug[p.slug].id),
            "reason": p.reason,
        }
        for p in plan.picks
        if p.slug in by_slug
    ]
    return {"picks": picks, "new_idea": plan.new_idea.model_dump()}


@router.post("/match-products")
async def match_products(
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    """Suggest catalog products for this week's unmatched lines. The cook applies them."""
    lst = await lists_svc.current_list(db, user)
    unmatched = [i for i in lst.items if not i.have and not i.product_id]
    if not unmatched:
        return {"matches": []}
    products = list(await db.scalars(select(Product).where(Product.user_id == user.id)))
    if not products:
        return {"matches": []}
    catalog = "\n".join(f"- {p.asin}: {p.title} ({p.size_text or ''})" for p in products)
    items = "\n".join(
        f"- key={i.key}; line='{i.name}'; needs {i.amount_text or '?'}" for i in unmatched
    )
    system = recipe_system(
        user,
        (
            "Match each shopping line to the best product from the cook's Whole Foods catalog. Match the "
            "form exactly (links vs ground, boneless vs bone-in, shredded vs block). If nothing fits, "
            "return an empty asin.\n\nCatalog:\n" + catalog
        ),
    )
    try:
        result = await ai.parse(
            db, user, ProductMatches, system=system, content=items, purpose="match_products"
        )
    except ai.AIError as exc:
        _raise(exc)
    by_asin = {p.asin: p for p in products}
    by_key = {i.key: i for i in unmatched}
    out = []
    for m in result.matches:
        if m.asin in by_asin and m.item_key in by_key:
            p = by_asin[m.asin]
            out.append(
                {
                    "item_id": str(by_key[m.item_key].id),
                    "item_name": by_key[m.item_key].name,
                    "product": {
                        "id": str(p.id),
                        "asin": p.asin,
                        "title": p.title,
                        "size_text": p.size_text,
                    },
                    "confidence": m.confidence,
                    "reason": m.reason,
                }
            )
    return {"matches": out}


# --- chat -----------------------------------------------------------------------------------


def _thread_out(t: ChatThread) -> dict:
    return {
        "id": str(t.id),
        "title": t.title,
        "updated_at": t.updated_at.isoformat(),
        "messages": [
            {"id": str(m.id), "role": m.role, **(m.display or {})}
            for m in t.messages
            if m.display is not None
        ],
    }


@router.get("/chat/threads")
async def list_threads(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    rows = await db.scalars(
        select(ChatThread)
        .where(ChatThread.user_id == user.id)
        .order_by(ChatThread.updated_at.desc())
        .limit(50)
    )
    return [
        {"id": str(t.id), "title": t.title, "updated_at": t.updated_at.isoformat()} for t in rows
    ]


@router.get("/chat/threads/{thread_id}")
async def get_thread(
    thread_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    t = await db.scalar(
        select(ChatThread).where(ChatThread.id == thread_id, ChatThread.user_id == user.id)
    )
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chat not found")
    return _thread_out(t)


@router.delete("/chat/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread(
    thread_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    t = await db.scalar(
        select(ChatThread).where(ChatThread.id == thread_id, ChatThread.user_id == user.id)
    )
    if t:
        await db.delete(t)


def _blocks(response) -> list[dict]:
    return [b.model_dump(exclude_none=True) for b in response.content]


@router.post("/chat")
async def chat(
    payload: ChatIn, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    if not user.anthropic_key_enc:
        _raise(ai.NoKeyError())
    if payload.thread_id:
        thread = await db.scalar(
            select(ChatThread).where(
                ChatThread.id == payload.thread_id, ChatThread.user_id == user.id
            )
        )
        if not thread:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Chat not found")
    else:
        thread = ChatThread(user_id=user.id, title=payload.message[:80])
        db.add(thread)
        await db.flush()
        await db.refresh(thread)

    system = recipe_system(user, CHAT_TASK)
    if payload.recipe_slug:
        try:
            recipe = await recipes_svc.get_visible(db, payload.recipe_slug, user)
            system += f"\n\nThe cook is looking at this recipe (slug {recipe.slug}):\n\n{recipes_svc.recipe_markdown(recipe)}"
        except HTTPException:
            pass

    history: list[dict] = []
    for m in thread.messages:  # replay, merging same-role turns so roles alternate
        if history and history[-1]["role"] == m.role:
            history[-1] = {"role": m.role, "content": [*history[-1]["content"], *m.content]}
        else:
            history.append({"role": m.role, "content": list(m.content)})
    user_msg = ChatMessage(
        thread_id=thread.id,
        role="user",
        content=[{"type": "text", "text": payload.message}],
        display={"text": payload.message},
    )
    db.add(user_msg)
    if history and history[-1]["role"] == "user":
        messages = [
            *history[:-1],
            {"role": "user", "content": [*history[-1]["content"], *user_msg.content]},
        ]
    else:
        messages = [*history, {"role": "user", "content": user_msg.content}]
    actions: list[dict] = []
    reply_text = ""
    last_assistant: ChatMessage | None = None
    try:
        for _ in range(MAX_TOOL_ROUNDS):
            response = await ai.create(
                db, user, system=system, messages=messages, tools=TOOLS, purpose="chat"
            )
            blocks = _blocks(response)
            messages.append({"role": "assistant", "content": blocks})
            text = "\n".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()
            tool_uses = [b for b in blocks if b.get("type") == "tool_use"]
            last_assistant = ChatMessage(
                thread_id=thread.id, role="assistant", content=blocks, display=None
            )
            db.add(last_assistant)
            if text:
                reply_text = text
            if not tool_uses:
                break
            results = []
            for tu in tool_uses:
                try:
                    result, action = await run_tool(
                        db, user, tu["name"], tu.get("input") or {}, prompt=payload.message
                    )
                    if action:
                        actions.append(action)
                    results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tu["id"],
                            "content": json.dumps(result, default=str)[:20000],
                        }
                    )
                except HTTPException as exc:
                    results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tu["id"],
                            "content": exc.detail,
                            "is_error": True,
                        }
                    )
                except Exception as exc:  # noqa: BLE001 — a tool bug must not lose the whole turn
                    results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tu["id"],
                            "content": f"Tool failed: {type(exc).__name__}",
                            "is_error": True,
                        }
                    )
            messages.append({"role": "user", "content": results})
            db.add(ChatMessage(thread_id=thread.id, role="user", content=results, display=None))
        else:
            reply_text = (
                reply_text or "I ran out of steps on that one; try asking a narrower question."
            )
    except ai.AIError as exc:
        await db.rollback()
        _raise(exc)

    if last_assistant is not None:
        last_assistant.display = {"text": reply_text or "Done.", "actions": actions}
    thread.updated_at = func.now()
    await db.flush()
    await db.refresh(thread)
    return _thread_out(thread)
