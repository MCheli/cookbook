"""First start: the site owner gets the bundled recipes; dev gets a password user.

`app/seed/recipes.json` holds the 38 recipes that used to live as markdown files in the repo,
verbatim. They are imported once, owned by the first COOKBOOK_OWNER_EMAILS address (a user row is
created for it so Google sign-in later attaches to the same account by email).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import hash_password
from app.models import Recipe, SiteState, User
from app.schemas import RecipeIn
from app.services.recipe_markdown import parse_markdown
from app.services.recipes import apply_payload, unique_slug

logger = logging.getLogger("cookbook.seed")

SEED_FILE = Path(__file__).resolve().parent.parent / "seed" / "recipes.json"
SEED_STATE_KEY = "bundled_recipes_imported"


def bundled_recipes() -> list[dict]:
    return json.loads(SEED_FILE.read_text(encoding="utf-8"))


_TAG_WORDS = {
    "chicken": ("chicken",),
    "beef": ("beef", "chuck", "steak", "roast"),
    "pork": ("pork",),
    "sausage": ("sausage", "kielbasa"),
    "shrimp": ("shrimp",),
    "salmon": ("salmon",),
    "pasta": ("pasta", "penne", "rigatoni", "noodle", "macaroni", "spaghetti"),
    "rice": ("rice",),
    "eggs": ("egg ", "eggs"),
    "spicy": (
        "jalapeño",
        "jalapeno",
        "sriracha",
        "gochujang",
        "harissa",
        "jerk",
        "chipotle",
        "buffalo",
    ),
}


def auto_tags(doc, method: str) -> list[str]:
    """Filter tags for the bundled recipes, from their ingredients and method."""
    items = [
        i.item.lower() + " "
        for i in doc.ingredients
        if not any(w in i.item.lower() for w in ("broth", "stock", "bouillon", "egg noodle"))
    ]
    text = " ".join(items) + " " + doc.title.lower() + " "
    tags = {tag for tag, words in _TAG_WORDS.items() if any(w in text for w in words)}
    if method in ("instapot", "crockpot"):
        tags.add("dump-and-go")
    return sorted(tags)


def recipe_in_from_markdown(markdown: str, method: str, **extra) -> RecipeIn:
    doc = parse_markdown(markdown)
    extra.setdefault("tags", auto_tags(doc, method))
    return RecipeIn(
        title=doc.title,
        emoji=doc.emoji,
        method=method,
        servings_text=doc.servings_text,
        prep_text=doc.prep_text,
        cook_text=doc.cook_text,
        ingredients=[
            {"group": i.group, "item": i.item, "amount": i.amount} for i in doc.ingredients
        ],
        steps=doc.steps,
        grocery=doc.grocery,
        **extra,
    )


async def import_markdown_recipe(
    db: AsyncSession, owner: User, markdown: str, method: str, **extra
) -> Recipe:
    data = recipe_in_from_markdown(markdown, method, **extra)
    recipe = Recipe(owner_id=owner.id, slug=await unique_slug(db, data.title), source=data.source)
    apply_payload(recipe, data, owner)
    recipe.source_markdown = markdown
    db.add(recipe)
    await db.flush()
    return recipe


async def get_or_create_user(db: AsyncSession, email: str, name: str | None = None) -> User:
    user = await db.scalar(select(User).where(User.email == email.lower()))
    if user is None:
        user = User(email=email.lower(), display_name=name, preferences={})
        db.add(user)
        await db.flush()
    return user


async def seed_owner_recipes(db: AsyncSession) -> int:
    """Import the bundled recipes once, for the first owner. Returns how many were imported."""
    if settings.DEMO_MODE or not settings.owner_emails:
        return 0
    if await db.get(SiteState, SEED_STATE_KEY):
        return 0
    owner = await get_or_create_user(db, settings.owner_emails[0])
    count = 0
    for entry in bundled_recipes():
        await import_markdown_recipe(
            db, owner, entry["markdown"], entry["method"], source="original", visibility="public"
        )
        count += 1
    db.add(SiteState(key=SEED_STATE_KEY, value={"count": count, "owner": owner.email}))
    await db.flush()
    logger.info("Imported %d bundled recipes for %s", count, owner.email)
    return count


async def ensure_test_user(db: AsyncSession) -> None:
    if settings.DEMO_MODE or not (settings.TEST_USER_EMAIL and settings.TEST_USER_PASSWORD):
        return
    user = await get_or_create_user(db, settings.TEST_USER_EMAIL, "Test user")
    if not user.hashed_password:
        user.hashed_password = hash_password(settings.TEST_USER_PASSWORD)


async def run_startup_seed() -> None:
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        await ensure_test_user(db)
        await seed_owner_recipes(db)
        await db.commit()
