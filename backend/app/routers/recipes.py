"""Recipes: public browsing, the signed-in user's own recipes, exports (markdown, JSON-LD, PDF)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user, get_optional_user
from app.models import CookLog, Recipe, SavedRecipe, User
from app.schemas import Method, RecipeIn
from app.services import recipes as svc
from app.services.pdf import render_pdf
from app.services.quantities import scale_amount
from app.services.recipe_markdown import to_markdown
from app.services.seed import import_markdown_recipe

router = APIRouter()


async def _saved_ids(db: AsyncSession, viewer: User | None) -> set[UUID]:
    if not viewer:
        return set()
    return set(
        await db.scalars(select(SavedRecipe.recipe_id).where(SavedRecipe.user_id == viewer.id))
    )


async def _detail(db: AsyncSession, recipe: Recipe, viewer: User | None) -> dict:
    owner = await db.get(User, recipe.owner_id)
    parent = await db.get(Recipe, recipe.parent_id) if recipe.parent_id else None
    if parent and not svc.can_view(parent, viewer):
        parent = None
    variants = list(
        await db.scalars(
            select(Recipe)
            .where(Recipe.parent_id == recipe.id, svc.visible_clause(viewer))
            .order_by(Recipe.created_at)
        )
    )
    saved = recipe.id in await _saved_ids(db, viewer)
    data = svc.detail(
        recipe,
        viewer,
        owner_name=(owner.display_name or "Mark") if owner and svc.is_owner_user(owner) else None,
        parent=parent,
        variants=variants,
        saved=saved,
    )
    if viewer:
        logs = await db.scalars(
            select(CookLog)
            .where(CookLog.user_id == viewer.id, CookLog.recipe_id == recipe.id)
            .order_by(CookLog.cooked_on.desc())
            .limit(10)
        )
        data["cook_log"] = [
            {
                "id": str(c.id),
                "cooked_on": c.cooked_on.isoformat(),
                "rating": c.rating,
                "notes": c.notes,
            }
            for c in logs
        ]
    return data


@router.get("")
async def list_recipes(
    q: str | None = None,
    method: Method | None = None,
    tag: str | None = None,
    scope: str = Query("all", pattern="^(all|mine|saved|public)$"),
    db: AsyncSession = Depends(get_db),
    viewer: User | None = Depends(get_optional_user),
) -> list[dict]:
    query = select(Recipe).where(svc.visible_clause(viewer if scope != "public" else None))
    saved = await _saved_ids(db, viewer)
    if scope == "mine" and viewer:
        query = query.where(Recipe.owner_id == viewer.id)
    elif scope == "saved":
        query = query.where(Recipe.id.in_(saved or {UUID(int=0)}))
    if scope in ("all", "public") or not viewer:
        # Drafts never show in the shared grid; they live under "mine".
        query = query.where(
            (Recipe.status == "published") | (Recipe.owner_id == (viewer.id if viewer else None))
        )
    if method:
        query = query.where(Recipe.method == method)
    if tag:
        query = query.where(Recipe.tags.any(tag.lower()))
    rows = list(await db.scalars(query.order_by(Recipe.title)))
    if q:
        needle = q.lower()
        rows = [
            r
            for r in rows
            if needle in r.title.lower()
            or any(needle in i.item.lower() for i in r.ingredients)
            or any(needle in t for t in r.tags)
        ]
    return [svc.summary(r, viewer, saved) for r in rows]


@router.get("/tags")
async def list_tags(
    db: AsyncSession = Depends(get_db), viewer: User | None = Depends(get_optional_user)
):
    tags = await db.scalars(select(Recipe.tags).where(svc.visible_clause(viewer)))
    return sorted({t for row in tags for t in row})


@router.get("/pdf")
async def recipes_pdf(
    slugs: str,
    factor: float = Query(1.0, ge=0.25, le=8),
    db: AsyncSession = Depends(get_db),
    viewer: User | None = Depends(get_optional_user),
) -> Response:
    """One PDF, one recipe per page: what the grocery skill prints for the week."""
    wanted = [s for s in slugs.split(",") if s][:20]
    if not wanted:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No recipes named")
    markdowns = [_scaled_markdown(await svc.get_visible(db, s, viewer), factor) for s in wanted]
    return Response(
        render_pdf(markdowns),
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="recipes.pdf"'},
    )


def _scaled_markdown(recipe: Recipe, factor: float) -> str:
    doc = svc.doc_from_recipe(recipe)
    if factor != 1:
        for ing in doc.ingredients:
            ing.amount = scale_amount(ing.amount, factor)
        doc.servings_text = f"{doc.servings_text or ''} (×{factor:g})".strip()
    return to_markdown(doc)


@router.get("/{slug}")
async def get_recipe(
    slug: str, db: AsyncSession = Depends(get_db), viewer: User | None = Depends(get_optional_user)
):
    return await _detail(db, await svc.get_visible(db, slug, viewer), viewer)


@router.get("/{slug}/markdown", response_class=PlainTextResponse)
async def recipe_markdown(
    slug: str, db: AsyncSession = Depends(get_db), viewer: User | None = Depends(get_optional_user)
):
    recipe = await svc.get_visible(db, slug, viewer)
    return PlainTextResponse(svc.recipe_markdown(recipe), media_type="text/markdown; charset=utf-8")


@router.get("/{slug}/jsonld")
async def recipe_jsonld(
    slug: str, db: AsyncSession = Depends(get_db), viewer: User | None = Depends(get_optional_user)
):
    recipe = await svc.get_visible(db, slug, viewer)
    owner = await db.get(User, recipe.owner_id)
    return svc.jsonld(recipe, owner.display_name if owner and svc.is_owner_user(owner) else None)


@router.get("/{slug}/pdf")
async def recipe_pdf(
    slug: str,
    factor: float = Query(1.0, ge=0.25, le=8),
    db: AsyncSession = Depends(get_db),
    viewer: User | None = Depends(get_optional_user),
) -> Response:
    recipe = await svc.get_visible(db, slug, viewer)
    return Response(
        render_pdf([_scaled_markdown(recipe, factor)]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{recipe.slug}.pdf"'},
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_recipe(
    payload: RecipeIn, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    if payload.parent_id:
        parent = await svc.get_visible(db, str(payload.parent_id), user)
        payload.parent_id = parent.id
    recipe = Recipe(
        owner_id=user.id,
        slug=await svc.unique_slug(db, payload.title),
        source=payload.source if payload.source != "original" else "manual",
        source_url=payload.source_url,
        parent_id=payload.parent_id,
        ai_meta=payload.ai_meta,
    )
    svc.apply_payload(recipe, payload, user)
    db.add(recipe)
    await db.flush()
    await db.refresh(recipe)
    return await _detail(db, recipe, user)


@router.put("/{recipe_id}")
async def update_recipe(
    recipe_id: UUID,
    payload: RecipeIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    recipe = await svc.get_own(db, recipe_id, user)
    if payload.title.strip() != recipe.title:
        recipe.slug = await svc.unique_slug(db, payload.title, exclude_id=recipe.id)
    svc.apply_payload(recipe, payload, user)
    recipe.updated_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(recipe)
    return await _detail(db, recipe, user)


@router.delete("/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recipe(
    recipe_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    recipe = await svc.get_own(db, recipe_id, user)
    recipe.deleted_at = datetime.now(UTC)


@router.post("/{recipe_id}/copy", status_code=status.HTTP_201_CREATED)
async def copy_recipe(
    recipe_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    """Make a private, editable copy (a variant linked to the original)."""
    original = await svc.get_visible(db, str(recipe_id), user)
    data = svc.payload_from_recipe(original)
    data.visibility, data.status = "private", "published"
    copy = Recipe(
        owner_id=user.id,
        slug=await svc.unique_slug(db, data.title),
        source="remix",
        parent_id=original.id,
    )
    svc.apply_payload(copy, data, user)
    copy.visibility = "private"
    db.add(copy)
    await db.flush()
    await db.refresh(copy)
    return await _detail(db, copy, user)


@router.put("/{recipe_id}/save", status_code=status.HTTP_204_NO_CONTENT)
async def save_recipe(
    recipe_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    recipe = await svc.get_visible(db, str(recipe_id), user)
    if not await db.get(SavedRecipe, (user.id, recipe.id)):
        db.add(SavedRecipe(user_id=user.id, recipe_id=recipe.id))


@router.delete("/{recipe_id}/save", status_code=status.HTTP_204_NO_CONTENT)
async def unsave_recipe(
    recipe_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    row = await db.get(SavedRecipe, (user.id, recipe_id))
    if row:
        await db.delete(row)


class MarkdownImport(BaseModel):
    markdown: str = Field(min_length=10, max_length=50_000)
    method: Method = "stovetop-oven"


@router.post("/import/markdown", status_code=status.HTTP_201_CREATED)
async def import_markdown(
    payload: MarkdownImport,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Add a recipe written in the cookbook's original markdown format."""
    try:
        recipe = await import_markdown_recipe(
            db, user, payload.markdown, payload.method, source="import"
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    await db.refresh(recipe)
    return await _detail(db, recipe, user)
