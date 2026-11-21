"""Tools the chat assistant can use. Each runs as the signed-in user, inside their own data.

A tool returns (result_for_claude, action_for_ui). Actions are rendered as cards under the
assistant's reply (a saved draft, a list change), so the cook sees what actually happened.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.schemas import RecipeDraft
from app.config import settings
from app.models import CookLog, Recipe, ShoppingListItem, ShoppingListRecipe, User
from app.schemas import RecipeIn
from app.services import lists as lists_svc
from app.services import recipes as recipes_svc

_DRAFT_SCHEMA = RecipeDraft.model_json_schema()

TOOLS: list[dict[str, Any]] = [
    {
        "name": "search_recipes",
        "description": "Search the cookbook (the cook's own recipes and the public ones) by words in the title, ingredients or tags. Empty query lists everything.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "method": {
                    "type": "string",
                    "enum": ["instapot", "crockpot", "stovetop-oven", "other"],
                },
            },
        },
    },
    {
        "name": "get_recipe",
        "description": "Read one recipe in full, by slug.",
        "input_schema": {
            "type": "object",
            "properties": {"slug": {"type": "string"}},
            "required": ["slug"],
        },
    },
    {
        "name": "create_recipe_draft",
        "description": "Save a new recipe (or a changed version of an existing one) as a private draft the cook can review, edit and publish. Pass based_on_slug when it is a version of an existing recipe.",
        "input_schema": {
            "type": "object",
            "properties": {
                "recipe": _DRAFT_SCHEMA,
                "based_on_slug": {"type": "string"},
            },
            "required": ["recipe"],
            **({"$defs": _DRAFT_SCHEMA.pop("$defs")} if "$defs" in _DRAFT_SCHEMA else {}),
        },
    },
    {
        "name": "get_shopping_list",
        "description": "This week's shopping list: its recipes and the items still needed.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "add_recipe_to_list",
        "description": "Add a recipe to this week's shopping list (its ingredients are added automatically).",
        "input_schema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string"},
                "servings_factor": {"type": "number", "description": "1 = as written, 2 = double"},
            },
            "required": ["slug"],
        },
    },
    {
        "name": "remove_recipe_from_list",
        "description": "Take a recipe off this week's shopping list.",
        "input_schema": {
            "type": "object",
            "properties": {"slug": {"type": "string"}},
            "required": ["slug"],
        },
    },
    {
        "name": "add_list_item",
        "description": "Add a single extra item to this week's shopping list.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}, "amount": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "get_cook_history",
        "description": "What the cook made recently (most recent first), with ratings and notes.",
        "input_schema": {"type": "object", "properties": {"limit": {"type": "integer"}}},
    },
]


def draft_to_payload(
    draft: RecipeDraft, *, parent_id=None, prompt: str | None = None, model: str | None = None
) -> RecipeIn:
    from datetime import UTC, datetime

    return RecipeIn(
        title=draft.title,
        emoji=draft.emoji,
        method=draft.method,
        description=draft.description or None,
        servings_text=draft.servings_text,
        prep_text=draft.prep_text,
        cook_text=draft.cook_text,
        tags=draft.tags[:20],
        visibility="private",
        status="draft",
        notes=draft.notes or None,
        ingredients=[i.model_dump() for i in draft.ingredients][:80],
        steps=draft.steps[:60],
        grocery=draft.grocery[:40],
        parent_id=parent_id,
        source="remix" if parent_id else "ai",
        ai_meta={
            "model": model or settings.AI_MODEL,
            "prompt": (prompt or "")[:1000],
            "created_at": datetime.now(UTC).isoformat(),
        },
    )


async def save_draft(db: AsyncSession, user: User, payload: RecipeIn) -> Recipe:
    recipe = Recipe(
        owner_id=user.id,
        slug=await recipes_svc.unique_slug(db, payload.title),
        source=payload.source,
        parent_id=payload.parent_id,
        ai_meta=payload.ai_meta,
    )
    recipes_svc.apply_payload(recipe, payload, user)
    db.add(recipe)
    await db.flush()
    return recipe


async def run_tool(
    db: AsyncSession, user: User, name: str, args: dict, *, prompt: str
) -> tuple[Any, dict | None]:
    if name == "search_recipes":
        q = (args.get("query") or "").lower()
        query = select(Recipe).where(recipes_svc.visible_clause(user))
        if args.get("method"):
            query = query.where(Recipe.method == args["method"])
        rows = [
            r
            for r in await db.scalars(query.order_by(Recipe.title))
            if not q
            or q in r.title.lower()
            or any(q in i.item.lower() for i in r.ingredients)
            or any(q in t for t in r.tags)
        ]
        return [
            {
                "slug": r.slug,
                "title": r.title,
                "method": r.method,
                "tags": r.tags,
                "mine": r.owner_id == user.id,
                "status": r.status,
            }
            for r in rows[:60]
        ], None

    if name == "get_recipe":
        recipe = await recipes_svc.get_visible(db, str(args.get("slug", "")), user)
        return {
            "slug": recipe.slug,
            "markdown": recipes_svc.recipe_markdown(recipe),
            "notes": recipe.notes,
        }, None

    if name == "create_recipe_draft":
        draft = RecipeDraft.model_validate(args.get("recipe") or {})
        parent = None
        if args.get("based_on_slug"):
            parent = await recipes_svc.get_visible(db, args["based_on_slug"], user)
        recipe = await save_draft(
            db,
            user,
            draft_to_payload(draft, parent_id=parent.id if parent else None, prompt=prompt),
        )
        return {"saved": True, "slug": recipe.slug, "status": "draft"}, {
            "type": "draft",
            "slug": recipe.slug,
            "title": recipe.title,
            "emoji": recipe.emoji,
            "based_on": parent.title if parent else None,
        }

    lst = await lists_svc.current_list(db, user)

    if name == "get_shopping_list":
        data = await lists_svc.serialize(db, lst, user)
        need = [
            f"{i['name']} ({i['amount_text'] or ''})"
            for a in data["aisles"]
            for i in a["items"]
            if not i["have"]
        ]
        return {"recipes": [r["title"] for r in data["recipes"]], "still_needed": need}, None

    if name in ("add_recipe_to_list", "remove_recipe_from_list"):
        recipe = await recipes_svc.get_visible(db, str(args.get("slug", "")), user)
        if name == "add_recipe_to_list":
            factor = float(args.get("servings_factor") or 1)
            factor = min(max(factor, 0.25), 8)
            row = next((r for r in lst.recipes if r.recipe_id == recipe.id), None)
            if row:
                row.servings_factor = factor
            else:
                lst.recipes.append(
                    ShoppingListRecipe(
                        list_id=lst.id,
                        recipe_id=recipe.id,
                        servings_factor=factor,
                        position=len(lst.recipes),
                    )
                )
            message = f"Added {recipe.title} to this week's list" + (
                f" (×{factor:g})" if factor != 1 else ""
            )
        else:
            lst.recipes = [r for r in lst.recipes if r.recipe_id != recipe.id]
            message = f"Took {recipe.title} off this week's list"
        await db.flush()
        await lists_svc.rebuild(db, lst, user)
        return {"ok": True, "message": message}, {"type": "list", "message": message}

    if name == "add_list_item":
        item_name = str(args.get("name", "")).strip()[:240]
        if not item_name:
            return {"ok": False, "error": "name is required"}, None
        key = lists_svc.manual_key(item_name)
        if not any(i.key == key for i in lst.items):
            lst.items.append(
                ShoppingListItem(
                    list_id=lst.id,
                    key=key,
                    name=item_name,
                    aisle="Other",
                    amount_text=(args.get("amount") or None),
                    source="manual",
                    position=2000 + len(lst.items),
                )
            )
            await db.flush()
        message = f"Added {item_name} to the list"
        return {"ok": True, "message": message}, {"type": "list", "message": message}

    if name == "get_cook_history":
        limit = min(int(args.get("limit") or 20), 60)
        rows = (
            await db.execute(
                select(CookLog, Recipe.title, Recipe.slug)
                .join(Recipe, Recipe.id == CookLog.recipe_id)
                .where(CookLog.user_id == user.id)
                .order_by(CookLog.cooked_on.desc())
                .limit(limit)
            )
        ).all()
        return [
            {
                "date": c.cooked_on.isoformat(),
                "title": t,
                "slug": s,
                "rating": c.rating,
                "notes": c.notes,
            }
            for c, t, s in rows
        ], None

    return {"error": f"unknown tool {name}"}, None
