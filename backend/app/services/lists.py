"""The shopping list: recipes for the week, combined lines, products, and the Whole Foods cart.

Recipe lines are rebuilt from the list's recipes whenever they change. What the user decided about
a line (have it, which product, how many) is stored on the line and keyed by the ingredient key,
so it survives the rebuild. Lines whose recipes left the list disappear; manual and "regular"
lines stay until removed.
"""

from __future__ import annotations

from datetime import date
from urllib.parse import quote
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Product, Recipe, ShoppingList, ShoppingListItem, User
from app.services.grocery import (
    aisle_sort_key,
    combine,
    ingredient_key,
    whole_foods_search_url,
    whole_foods_search_url_for_product,
)

WHOLE_FOODS_BRAND = "VUZHIFdob2xlIEZvb2Rz"
CART_URL = f"https://www.amazon.com/cart/localmarket?almBrandId={WHOLE_FOODS_BRAND}"


def product_url(asin: str) -> str:
    return f"https://www.amazon.com/dp/{asin}?fpw=alm&almBrandId={WHOLE_FOODS_BRAND}"


async def current_list(db: AsyncSession, user: User) -> ShoppingList:
    lst = await db.scalar(
        select(ShoppingList)
        .where(ShoppingList.user_id == user.id, ShoppingList.status == "active")
        .order_by(ShoppingList.created_at.desc())
    )
    if lst is None:
        lst = ShoppingList(
            user_id=user.id, title=f"Week of {date.today():%b} {date.today().day}", status="active"
        )
        db.add(lst)
        await db.flush()
        await db.refresh(lst)
    return lst


async def products_by_key(db: AsyncSession, user: User) -> dict[str, Product]:
    out: dict[str, Product] = {}
    rows = await db.scalars(
        select(Product).where(Product.user_id == user.id).order_by(Product.purchase_count.desc())
    )
    for p in rows:
        for k in p.match_keys:
            out.setdefault(k, p)  # most-bought product wins a shared key
    return out


async def rebuild(db: AsyncSession, lst: ShoppingList, user: User) -> None:
    recipe_ids = [r.recipe_id for r in lst.recipes]
    recipes = (
        {r.id: r for r in await db.scalars(select(Recipe).where(Recipe.id.in_(recipe_ids)))}
        if recipe_ids
        else {}
    )
    lines = combine(
        [(recipes[r.recipe_id], r.servings_factor) for r in lst.recipes if r.recipe_id in recipes]
    )
    by_key = {i.key: i for i in lst.items}
    matches = await products_by_key(db, user)
    wanted = set()
    for n, line in enumerate(lines):
        wanted.add(line.key)
        item = by_key.get(line.key)
        if item is None:
            product = matches.get(line.key)
            item = ShoppingListItem(
                list_id=lst.id,
                key=line.key,
                have=line.likely_on_hand,
                quantity=1,
                product_id=product.id if product else None,
            )
            lst.items.append(item)
        elif item.product_id is None and line.key in matches:
            item.product_id = matches[line.key].id  # a product learned since the line was made
        item.name, item.aisle, item.amount_text = line.name, line.aisle, line.amount_text
        item.recipe_titles, item.position = line.recipe_titles, n
        item.source = "recipe"
    for item in list(lst.items):
        if item.source == "recipe" and item.key not in wanted:
            lst.items.remove(item)
    await db.flush()


async def fill_matches(db: AsyncSession, lst: ShoppingList, user: User) -> None:
    """Give unmatched lines a product if the catalog has learned one (e.g. after a history import)."""
    missing = [i for i in lst.items if i.product_id is None and not i.have]
    if not missing:
        return
    matches = await products_by_key(db, user)
    for item in missing:
        key = item.key.removeprefix("manual:")
        if key in matches:
            item.product_id = matches[key].id
    await db.flush()


async def add_regulars(db: AsyncSession, lst: ShoppingList, user: User) -> int:
    regulars = await db.scalars(
        select(Product).where(Product.user_id == user.id, Product.is_regular.is_(True))
    )
    existing = {i.key for i in lst.items}
    added = 0
    for p in regulars:
        key = f"product:{p.asin}"
        if key in existing or any(i.product_id == p.id for i in lst.items):
            continue
        lst.items.append(
            ShoppingListItem(
                list_id=lst.id,
                key=key,
                name=p.title,
                aisle="Regulars",
                source="regular",
                product_id=p.id,
                quantity=p.regular_qty,
                position=1000 + added,
            )
        )
        added += 1
    await db.flush()
    return added


def manual_key(name: str) -> str:
    return f"manual:{ingredient_key(name)}"


def _product_out(p: Product | None) -> dict | None:
    if not p:
        return None
    return {
        "id": str(p.id),
        "asin": p.asin,
        "title": p.title,
        "size_text": p.size_text,
        "price_cents": p.price_cents,
        "sold_by_weight": p.sold_by_weight,
        "notes": p.notes,
        "url": product_url(p.asin),
        # For when the old listing is gone (Whole Foods relists things under new ASINs).
        "search_url": whole_foods_search_url_for_product(p.title),
    }


async def serialize(db: AsyncSession, lst: ShoppingList, user: User) -> dict:
    recipe_ids = [r.recipe_id for r in lst.recipes]
    recipes = (
        {r.id: r for r in await db.scalars(select(Recipe).where(Recipe.id.in_(recipe_ids)))}
        if recipe_ids
        else {}
    )
    product_ids = [i.product_id for i in lst.items if i.product_id]
    products = (
        {p.id: p for p in await db.scalars(select(Product).where(Product.id.in_(product_ids)))}
        if product_ids
        else {}
    )

    aisles: dict[str, list[dict]] = {}
    for item in sorted(
        lst.items, key=lambda i: (aisle_sort_key(i.aisle), i.position, i.name.lower())
    ):
        aisles.setdefault(item.aisle, []).append(
            {
                "id": str(item.id),
                "key": item.key,
                "name": item.name,
                "aisle": item.aisle,
                "amount_text": item.amount_text,
                "recipe_titles": item.recipe_titles,
                "source": item.source,
                "have": item.have,
                "in_cart": item.in_cart,
                "quantity": item.quantity,
                "product": _product_out(products.get(item.product_id)),
                "search_url": whole_foods_search_url(item.name),
            }
        )
    need = [i for i in lst.items if not i.have]
    return {
        "id": str(lst.id),
        "title": lst.title,
        "status": lst.status,
        "recipes": [
            {
                "recipe_id": str(r.recipe_id),
                "slug": recipes[r.recipe_id].slug,
                "title": recipes[r.recipe_id].title,
                "emoji": recipes[r.recipe_id].emoji,
                "method": recipes[r.recipe_id].method,
                "servings_text": recipes[r.recipe_id].servings_text,
                "servings_factor": r.servings_factor,
            }
            for r in lst.recipes
            if r.recipe_id in recipes
        ],
        "aisles": [{"aisle": a, "items": items} for a, items in aisles.items()],
        "counts": {
            "total": len(lst.items),
            "need": len(need),
            "matched": sum(1 for i in need if i.product_id),
            "in_cart": sum(1 for i in need if i.in_cart),
        },
        "cart": cart_manifest(lst, products),
    }


def cart_manifest(lst: ShoppingList, products: dict[UUID, Product]) -> dict:
    """What goes into the Whole Foods cart: matched lines the user still needs and hasn't
    already added (ticked in cart on the list)."""
    items, unmatched = [], []
    seen: dict[str, dict] = {}
    for i in lst.items:
        if i.have or i.in_cart:
            continue
        p = products.get(i.product_id) if i.product_id else None
        if p is None:
            unmatched.append(
                {
                    "name": i.name,
                    "amount_text": i.amount_text,
                    "search_url": whole_foods_search_url(i.name),
                }
            )
            continue
        if p.asin in seen:  # two lines that map to one product
            seen[p.asin]["quantity"] = max(seen[p.asin]["quantity"], i.quantity)
            seen[p.asin]["for"].append(i.name)
            continue
        entry = {
            "asin": p.asin,
            # By-weight products go in at Amazon's default weight; the loader only steps counts.
            "quantity": 1 if p.sold_by_weight else i.quantity,
            "title": p.title,
            "for": [i.name],
            "url": product_url(p.asin),
        }
        seen[p.asin] = entry
        items.append(entry)
    return {
        "store": "Whole Foods Market (Amazon)",
        "cart_url": CART_URL,
        "loader_url": CART_URL + "#cookbook-cart=" + quote(_compact(items), safe=""),
        "items": items,
        "unmatched": unmatched,
    }


def _compact(items: list[dict]) -> str:
    """ASIN*qty pairs for the cart loader, in the URL fragment (never sent to Amazon's servers)."""
    return ",".join(f"{i['asin']}*{i['quantity']}" for i in items)
