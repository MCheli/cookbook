"""Grocery list preview (public), the signed-in shopping list, products, regulars, cook log."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.dependencies import get_current_user, get_optional_user
from app.models import (
    CookLog,
    Product,
    Recipe,
    ShoppingList,
    ShoppingListItem,
    ShoppingListRecipe,
    User,
)
from app.schemas import (
    CookLogIn,
    GroceryPreviewIn,
    ListItemIn,
    ListItemPatch,
    ListRecipeIn,
    ListRecipePatch,
    ProductIn,
    ProductPatch,
    PurchasesIn,
)
from app.services import lists as lists_svc
from app.services import recipes as recipes_svc
from app.services.grocery import combine, ingredient_key, whole_foods_search_url

router = APIRouter()


# --- public preview --------------------------------------------------------------------------


@router.post("/grocery/preview")
async def grocery_preview(
    payload: GroceryPreviewIn,
    db: AsyncSession = Depends(get_db),
    viewer: User | None = Depends(get_optional_user),
) -> dict:
    """The original site's flow: pick recipes, get one combined list with Whole Foods links."""
    recipes = [await recipes_svc.get_visible(db, s, viewer) for s in payload.recipe_slugs]
    lines = combine([(r, payload.factors.get(r.slug, 1.0)) for r in recipes])
    matches = await lists_svc.products_by_key(db, viewer) if viewer else {}
    aisles: dict[str, list[dict]] = {}
    for line in lines:
        p = matches.get(line.key)
        aisles.setdefault(line.aisle, []).append(
            {
                "key": line.key,
                "name": line.name,
                "amount_text": line.amount_text,
                "recipe_titles": line.recipe_titles,
                "likely_on_hand": line.likely_on_hand,
                "search_url": whole_foods_search_url(line.name),
                "product": (
                    {"asin": p.asin, "title": p.title, "url": lists_svc.product_url(p.asin)}
                    if p
                    else None
                ),
            }
        )
    return {
        "recipes": [{"slug": r.slug, "title": r.title, "emoji": r.emoji} for r in recipes],
        "aisles": [{"aisle": a, "items": items} for a, items in aisles.items()],
    }


# --- the shopping list ----------------------------------------------------------------------


async def _list_response(db: AsyncSession, lst: ShoppingList, user: User) -> dict:
    await db.refresh(lst)
    return await lists_svc.serialize(db, lst, user)


@router.get("/lists/current")
async def get_current_list(
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    lst = await lists_svc.current_list(db, user)
    if not settings.DEMO_MODE:  # the demo's sessions are read-only
        await lists_svc.fill_matches(db, lst, user)
    return await lists_svc.serialize(db, lst, user)


@router.get("/lists/current/cart")
async def get_cart(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """For agents (X-API-Key) and the cart loader: ASINs and quantities to add."""
    lst = await lists_svc.current_list(db, user)
    return (await lists_svc.serialize(db, lst, user))["cart"]


@router.post("/lists/current/recipes")
async def add_list_recipe(
    payload: ListRecipeIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    recipe = await recipes_svc.get_visible(db, str(payload.recipe_id), user)
    lst = await lists_svc.current_list(db, user)
    existing = next((r for r in lst.recipes if r.recipe_id == recipe.id), None)
    if existing:
        existing.servings_factor = payload.servings_factor
    else:
        lst.recipes.append(
            ShoppingListRecipe(
                list_id=lst.id,
                recipe_id=recipe.id,
                servings_factor=payload.servings_factor,
                position=len(lst.recipes),
            )
        )
    await db.flush()
    await lists_svc.rebuild(db, lst, user)
    return await _list_response(db, lst, user)


@router.patch("/lists/current/recipes/{recipe_id}")
async def patch_list_recipe(
    recipe_id: UUID,
    payload: ListRecipePatch,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    lst = await lists_svc.current_list(db, user)
    row = next((r for r in lst.recipes if r.recipe_id == recipe_id), None)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That recipe isn't on the list")
    row.servings_factor = payload.servings_factor
    await lists_svc.rebuild(db, lst, user)
    return await _list_response(db, lst, user)


@router.delete("/lists/current/recipes/{recipe_id}")
async def remove_list_recipe(
    recipe_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    lst = await lists_svc.current_list(db, user)
    lst.recipes = [r for r in lst.recipes if r.recipe_id != recipe_id]
    await db.flush()
    await lists_svc.rebuild(db, lst, user)
    return await _list_response(db, lst, user)


@router.post("/lists/current/regulars")
async def add_regulars(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    lst = await lists_svc.current_list(db, user)
    await lists_svc.add_regulars(db, lst, user)
    return await _list_response(db, lst, user)


async def _own_product(db: AsyncSession, user: User, product_id: UUID) -> Product:
    p = await db.scalar(select(Product).where(Product.id == product_id, Product.user_id == user.id))
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return p


@router.post("/lists/current/items")
async def add_list_item(
    payload: ListItemIn, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    lst = await lists_svc.current_list(db, user)
    key = lists_svc.manual_key(payload.name)
    if any(i.key == key for i in lst.items):
        raise HTTPException(status.HTTP_409_CONFLICT, "That's already on the list")
    product = await _own_product(db, user, payload.product_id) if payload.product_id else None
    if product is None:
        product = (await lists_svc.products_by_key(db, user)).get(ingredient_key(payload.name))
    lst.items.append(
        ShoppingListItem(
            list_id=lst.id,
            key=key,
            name=payload.name.strip(),
            aisle=(payload.aisle or "Other").strip(),
            amount_text=payload.amount_text,
            source="manual",
            quantity=payload.quantity,
            product_id=product.id if product else None,
            position=2000 + len(lst.items),
        )
    )
    await db.flush()
    return await _list_response(db, lst, user)


@router.patch("/lists/current/items/{item_id}")
async def patch_list_item(
    item_id: UUID,
    payload: ListItemPatch,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    lst = await lists_svc.current_list(db, user)
    item = next((i for i in lst.items if i.id == item_id), None)
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    if payload.have is not None:
        item.have = payload.have
    if payload.in_cart is not None:
        item.in_cart = payload.in_cart
    if payload.quantity is not None:
        item.quantity = payload.quantity
    if payload.clear_product:
        item.product_id = None
    elif payload.product_id:
        product = await _own_product(db, user, payload.product_id)
        item.product_id = product.id
        # Remember the choice: next time this ingredient matches the product on its own.
        if (
            payload.remember_match
            and item.source == "recipe"
            and item.key not in product.match_keys
        ):
            product.match_keys = [*product.match_keys, item.key]
    await db.flush()
    return await _list_response(db, lst, user)


@router.delete("/lists/current/items/{item_id}")
async def delete_list_item(
    item_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    lst = await lists_svc.current_list(db, user)
    item = next((i for i in lst.items if i.id == item_id), None)
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    if item.source == "recipe":  # it would come straight back on the next rebuild
        item.have = True
    else:
        lst.items.remove(item)
    await db.flush()
    return await _list_response(db, lst, user)


@router.post("/lists/current/complete")
async def complete_list(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """The order was placed: move it to history and start a fresh, empty one."""
    lst = await lists_svc.current_list(db, user)
    if lists_svc.is_empty(lst):
        raise HTTPException(status.HTTP_409_CONFLICT, "This order is empty.")
    lst.status, lst.ordered_at = "ordered", datetime.now(UTC)
    await db.flush()
    fresh = await lists_svc.current_list(db, user)
    return await lists_svc.serialize(db, fresh, user)


@router.post("/lists/{list_id}/reopen")
async def reopen_list(
    list_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    """Undo "I placed this order": make a past order current again, if the new one is still empty."""
    old = await db.get(ShoppingList, list_id)
    if old is None or old.user_id != user.id or old.status != "ordered":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    current = await lists_svc.current_list(db, user)
    if not lists_svc.is_empty(current):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Your current order already has things in it, so this one can't be reopened.",
        )
    await db.delete(current)
    old.status, old.ordered_at = "active", None
    await db.flush()
    return await _list_response(db, old, user)


@router.post("/lists/current/clear")
async def clear_list(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    lst = await lists_svc.current_list(db, user)
    lst.recipes, lst.items = [], []
    await db.flush()
    return await _list_response(db, lst, user)


@router.get("/lists/{list_id}/print")
async def list_print(
    list_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    """Every recipe of an order (current or past) in full, scaled factor included, so the page can
    print them straight from the tap (an iPhone won't print after waiting on the network)."""
    if list_id == "current":
        lst = await lists_svc.current_list(db, user)
    else:
        try:
            lst = await db.get(ShoppingList, UUID(list_id))
        except ValueError:
            lst = None
        if lst is None or lst.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    ids = [r.recipe_id for r in lst.recipes]
    found = (
        {r.id: r for r in await db.scalars(select(Recipe).where(Recipe.id.in_(ids)))} if ids else {}
    )
    out = []
    for r in lst.recipes:
        recipe = found.get(r.recipe_id)
        if recipe is None or not recipes_svc.can_view(recipe, user):
            continue
        data = recipes_svc.detail(
            recipe, user, owner_name=None, parent=None, variants=[], saved=False
        )
        data["factor"] = r.servings_factor
        out.append(data)
    return out


@router.get("/lists/history")
async def list_history(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    rows = await db.scalars(
        select(ShoppingList)
        .where(ShoppingList.user_id == user.id, ShoppingList.status == "ordered")
        .order_by(ShoppingList.ordered_at.desc().nulls_last())
        .limit(30)
    )
    out = []
    for lst in rows:
        recipes = await lists_svc.order_recipes(db, lst)
        out.append(
            {
                "id": str(lst.id),
                "title": lst.title,
                "created_at": lst.created_at.isoformat() if lst.created_at else None,
                "ordered_at": lst.ordered_at.isoformat() if lst.ordered_at else None,
                # Titles kept for older clients and agents; recipe_list has slugs and factors.
                "recipes": [r["title"] for r in recipes],
                "recipe_list": recipes,
                "items": len(lst.items),
            }
        )
    return out


# --- products (the Whole Foods catalog) ------------------------------------------------------


def product_out(p: Product) -> dict:
    return {
        "id": str(p.id),
        "asin": p.asin,
        "title": p.title,
        "brand": p.brand,
        "size_text": p.size_text,
        "price_cents": p.price_cents,
        "sold_by_weight": p.sold_by_weight,
        "notes": p.notes,
        "match_keys": p.match_keys,
        "is_regular": p.is_regular,
        "regular_qty": p.regular_qty,
        "purchase_count": p.purchase_count,
        "last_purchased_on": p.last_purchased_on.isoformat() if p.last_purchased_on else None,
        "source": p.source,
        "url": lists_svc.product_url(p.asin),
    }


def _clean_keys(keys: list[str]) -> list[str]:
    return sorted({ingredient_key(k) for k in keys if ingredient_key(k)})


@router.get("/products")
async def list_products(
    q: str | None = None,
    regulars: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Product).where(Product.user_id == user.id)
    if regulars:
        query = query.where(Product.is_regular.is_(True))
    if q:
        like = f"%{q.lower()}%"
        query = query.where(
            or_(
                Product.title.ilike(like),
                Product.match_keys.any(q.lower()),
                Product.asin == q.upper(),
            )
        )
    rows = await db.scalars(query.order_by(Product.purchase_count.desc(), Product.title))
    return [product_out(p) for p in rows]


@router.post("/products", status_code=status.HTTP_201_CREATED)
async def upsert_product(
    payload: ProductIn, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    p = await db.scalar(
        select(Product).where(Product.user_id == user.id, Product.asin == payload.asin)
    )
    data = payload.model_dump()
    data["match_keys"] = _clean_keys(payload.match_keys)
    if p is None:
        p = Product(user_id=user.id, source="manual", **data)
        db.add(p)
    else:
        for k, v in data.items():
            if k == "match_keys":
                v = sorted(set(p.match_keys) | set(v))
            setattr(p, k, v)
    await db.flush()
    return product_out(p)


@router.patch("/products/{product_id}")
async def patch_product(
    product_id: UUID,
    payload: ProductPatch,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    p = await _own_product(db, user, product_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(p, k, _clean_keys(v) if k == "match_keys" else v)
    await db.flush()
    return product_out(p)


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    await db.delete(await _own_product(db, user, product_id))


@router.post("/products/purchases")
async def record_purchases(
    payload: PurchasesIn, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    """Order history in bulk (an agent reading Whole Foods order pages). Safe to send twice:
    a product counts each distinct order date once."""
    created = updated = 0
    for line in payload.purchases:
        p = await db.scalar(
            select(Product).where(Product.user_id == user.id, Product.asin == line.asin)
        )
        if p is None:
            p = Product(
                user_id=user.id,
                asin=line.asin,
                title=line.title,
                source="history",
                match_keys=[],
                purchase_dates=[],
            )
            db.add(p)
            created += 1
        else:
            updated += 1
        dates = set(p.purchase_dates or [])
        dates.add(line.ordered_on)
        p.purchase_dates = sorted(dates)
        p.purchase_count = len(dates)
        p.last_purchased_on = max(dates)
        if line.price_cents is not None and (
            p.last_purchased_on == line.ordered_on or p.price_cents is None
        ):
            p.price_cents = line.price_cents
        p.size_text = p.size_text or line.size_text
        if line.match_keys:
            p.match_keys = sorted(set(p.match_keys or []) | set(_clean_keys(line.match_keys)))
        await db.flush()
    return {"created": created, "updated": updated}


# --- cook log ---------------------------------------------------------------------------------


@router.get("/cooklog")
async def get_cooklog(
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = (
        await db.execute(
            select(CookLog, Recipe.slug, Recipe.title, Recipe.emoji)
            .join(Recipe, Recipe.id == CookLog.recipe_id)
            .where(CookLog.user_id == user.id)
            .order_by(CookLog.cooked_on.desc(), CookLog.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [
        {
            "id": str(c.id),
            "recipe_id": str(c.recipe_id),
            "slug": slug,
            "title": title,
            "emoji": emoji,
            "cooked_on": c.cooked_on.isoformat(),
            "rating": c.rating,
            "notes": c.notes,
        }
        for c, slug, title, emoji in rows
    ]


@router.post("/cooklog", status_code=status.HTTP_201_CREATED)
async def add_cooklog(
    payload: CookLogIn, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    recipe = await recipes_svc.get_visible(db, str(payload.recipe_id), user)
    entry = CookLog(
        user_id=user.id,
        recipe_id=recipe.id,
        cooked_on=payload.cooked_on or date.today(),
        rating=payload.rating,
        notes=payload.notes,
    )
    db.add(entry)
    await db.flush()
    return {
        "id": str(entry.id),
        "cooked_on": entry.cooked_on.isoformat(),
        "rating": entry.rating,
        "notes": entry.notes,
    }


@router.delete("/cooklog/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cooklog(
    entry_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    entry = await db.scalar(
        select(CookLog).where(CookLog.id == entry_id, CookLog.user_id == user.id)
    )
    if not entry:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    await db.delete(entry)
