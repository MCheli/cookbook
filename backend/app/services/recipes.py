"""Recipe rules: slugs, who can see and change what, serialization, schema.org JSON-LD."""

from __future__ import annotations

import re
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Recipe, RecipeGroceryLine, RecipeIngredient, RecipeStep, User
from app.schemas import RecipeIn
from app.services.recipe_markdown import IngredientRow, RecipeDoc, to_markdown

METHODS = {
    "instapot": "Instant Pot",
    "crockpot": "Crockpot",
    "stovetop-oven": "Stovetop & Oven",
    "other": "Other",
}


def method_label(method: str) -> str:
    return METHODS.get(method, method.replace("-", " ").title())


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:140] or "recipe"


async def unique_slug(db: AsyncSession, title: str, exclude_id: UUID | None = None) -> str:
    base = slugify(title)
    slug, n = base, 2
    while True:
        q = select(Recipe.id).where(Recipe.slug == slug)
        if exclude_id:
            q = q.where(Recipe.id != exclude_id)
        if await db.scalar(q) is None:
            return slug
        slug, n = f"{base}-{n}", n + 1


def _first_number(text: str | None) -> float | None:
    if not text:
        return None
    m = re.search(r"\d+(?:\.\d+)?", text)
    return float(m.group()) if m else None


def _minutes(text: str | None) -> int | None:
    if not text:
        return None
    # Times are short ("1 hr 10 min"); the cap keeps the digit-run search cheap (py/polynomial-redos).
    t = text[:160].replace(" ", " ").lower()
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:[–-]\s*\d+(?:\.\d+)?\s*)?(hr|hour|h\b|min)", t)
    if not m:
        return None
    value = float(m.group(1))
    return int(value * 60) if m.group(2).startswith("h") else int(value)


# --- visibility -----------------------------------------------------------------------------


def is_owner_user(user: User | None) -> bool:
    return bool(user) and user.email.lower() in settings.owner_emails


def can_view(recipe: Recipe, viewer: User | None) -> bool:
    if recipe.deleted_at is not None:
        return False
    if viewer and recipe.owner_id == viewer.id:
        return True
    return recipe.visibility == "public" and recipe.status == "published"


def visible_clause(viewer: User | None):
    public = (Recipe.visibility == "public") & (Recipe.status == "published")
    if viewer is None:
        return public & Recipe.deleted_at.is_(None)
    return or_(public, Recipe.owner_id == viewer.id) & Recipe.deleted_at.is_(None)


async def get_visible(db: AsyncSession, slug_or_id: str, viewer: User | None) -> Recipe:
    q = select(Recipe)
    try:
        q = q.where(Recipe.id == UUID(slug_or_id))
    except ValueError:
        q = q.where(Recipe.slug == slug_or_id)
    recipe = await db.scalar(q)
    if not recipe or not can_view(recipe, viewer):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recipe not found")
    return recipe


async def get_own(db: AsyncSession, recipe_id: UUID, user: User) -> Recipe:
    recipe = await db.scalar(
        select(Recipe).where(
            Recipe.id == recipe_id, Recipe.owner_id == user.id, Recipe.deleted_at.is_(None)
        )
    )
    if not recipe:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recipe not found")
    return recipe


# --- writing ----------------------------------------------------------------------------------


def apply_payload(recipe: Recipe, data: RecipeIn, author: User) -> None:
    """Copy a payload onto a recipe. Only site owners can publish to the public cookbook."""
    recipe.title = data.title.strip()
    recipe.emoji = (data.emoji or "").strip() or None
    recipe.method = data.method
    recipe.description = data.description
    recipe.servings_text = data.servings_text
    recipe.prep_text = data.prep_text
    recipe.cook_text = data.cook_text
    recipe.servings_base = _first_number(data.servings_text)
    recipe.prep_minutes = _minutes(data.prep_text)
    recipe.cook_minutes = _minutes(data.cook_text)
    recipe.tags = sorted({t.strip().lower()[:40] for t in data.tags if t.strip()})
    recipe.visibility = data.visibility if is_owner_user(author) else "private"
    recipe.status = data.status
    recipe.notes = data.notes
    recipe.ingredients = [
        RecipeIngredient(
            position=i,
            group_name=(ing.group or "").strip() or None,
            item=ing.item.strip(),
            amount=(ing.amount or "").strip() or None,
        )
        for i, ing in enumerate(data.ingredients)
        if ing.item.strip()
    ]
    recipe.steps = [
        RecipeStep(position=i, text=s.strip()) for i, s in enumerate(data.steps) if s.strip()
    ]
    recipe.grocery = [
        RecipeGroceryLine(position=i, text=g.strip())
        for i, g in enumerate(data.grocery)
        if g.strip()
    ]


def payload_from_recipe(recipe: Recipe) -> RecipeIn:
    return RecipeIn(
        title=recipe.title,
        emoji=recipe.emoji,
        method=recipe.method if recipe.method in METHODS else "other",
        description=recipe.description,
        servings_text=recipe.servings_text,
        prep_text=recipe.prep_text,
        cook_text=recipe.cook_text,
        tags=recipe.tags,
        visibility=recipe.visibility,
        status=recipe.status,
        notes=recipe.notes,
        ingredients=[
            {"group": i.group_name, "item": i.item, "amount": i.amount} for i in recipe.ingredients
        ],
        steps=[s.text for s in recipe.steps],
        grocery=[g.text for g in recipe.grocery],
        source=(
            recipe.source
            if recipe.source in ("manual", "ai", "import", "remix", "original")
            else "manual"
        ),
        source_url=recipe.source_url,
        ai_meta=recipe.ai_meta,
    )


# --- reading ----------------------------------------------------------------------------------


def doc_from_recipe(recipe: Recipe) -> RecipeDoc:
    return RecipeDoc(
        title=recipe.title,
        emoji=recipe.emoji,
        servings_text=recipe.servings_text,
        prep_text=recipe.prep_text,
        cook_text=recipe.cook_text,
        ingredients=[IngredientRow(i.group_name, i.item, i.amount) for i in recipe.ingredients],
        steps=[s.text for s in recipe.steps],
        grocery=[g.text for g in recipe.grocery],
    )


def recipe_markdown(recipe: Recipe) -> str:
    return to_markdown(doc_from_recipe(recipe))


def summary(recipe: Recipe, viewer: User | None, saved_ids: set[UUID] | None = None) -> dict:
    return {
        "id": str(recipe.id),
        "slug": recipe.slug,
        "title": recipe.title,
        "emoji": recipe.emoji,
        "method": recipe.method,
        "method_label": method_label(recipe.method),
        "description": recipe.description,
        "servings_text": recipe.servings_text,
        "prep_text": recipe.prep_text,
        "cook_text": recipe.cook_text,
        "total_minutes": (recipe.prep_minutes or 0) + (recipe.cook_minutes or 0) or None,
        "tags": recipe.tags,
        "source": recipe.source,
        "visibility": recipe.visibility,
        "status": recipe.status,
        "is_mine": bool(viewer) and recipe.owner_id == viewer.id,
        "is_saved": bool(saved_ids) and recipe.id in saved_ids,
        "parent_id": str(recipe.parent_id) if recipe.parent_id else None,
        "ingredient_names": [i.item for i in recipe.ingredients],
        "updated_at": recipe.updated_at.isoformat() if recipe.updated_at else None,
    }


def detail(
    recipe: Recipe,
    viewer: User | None,
    *,
    owner_name: str | None,
    parent: Recipe | None,
    variants: list[Recipe],
    saved: bool,
) -> dict:
    data = summary(recipe, viewer, {recipe.id} if saved else set())
    data.update(
        {
            "notes": recipe.notes,
            "source_url": recipe.source_url,
            "ai_meta": recipe.ai_meta,
            "servings_base": recipe.servings_base,
            "ingredients": [
                {"group": i.group_name, "item": i.item, "amount": i.amount}
                for i in recipe.ingredients
            ],
            "steps": [s.text for s in recipe.steps],
            "grocery": [g.text for g in recipe.grocery],
            "owner_name": owner_name,
            "parent": {"slug": parent.slug, "title": parent.title} if parent else None,
            "variants": [{"slug": v.slug, "title": v.title, "source": v.source} for v in variants],
            "can_edit": bool(viewer) and recipe.owner_id == viewer.id,
            "can_publish": is_owner_user(viewer),
        }
    )
    return data


def _iso_duration(minutes: int | None) -> str | None:
    if not minutes:
        return None
    h, m = divmod(minutes, 60)
    return "PT" + (f"{h}H" if h else "") + (f"{m}M" if m else "")


def _plain(md: str) -> str:
    return re.sub(r"\*+([^*]+)\*+", r"\1", md)


def jsonld(recipe: Recipe, owner_name: str | None) -> dict:
    """schema.org/Recipe: the format recipe sites publish, used for export and on public pages."""
    data = {
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": recipe.title,
        "recipeCategory": method_label(recipe.method),
        "recipeYield": recipe.servings_text,
        "prepTime": _iso_duration(recipe.prep_minutes),
        "cookTime": _iso_duration(recipe.cook_minutes),
        "keywords": ", ".join(recipe.tags) or None,
        "description": recipe.description,
        "author": {"@type": "Person", "name": owner_name} if owner_name else None,
        "url": f"{settings.SITE_URL.rstrip('/')}/r/{recipe.slug}",
        "recipeIngredient": [
            " ".join(p for p in (i.amount, i.item) if p) for i in recipe.ingredients
        ],
        "recipeInstructions": [
            {"@type": "HowToStep", "position": n, "text": _plain(s.text)}
            for n, s in enumerate(recipe.steps, 1)
        ],
    }
    return {k: v for k, v in data.items() if v not in (None, "", [])}
