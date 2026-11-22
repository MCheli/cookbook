"""The API end to end against Postgres: public browsing, ownership, lists, products, the cart."""

from __future__ import annotations

from datetime import date

from tests.conftest import client_for, get_user, make_user

NEW_RECIPE = {
    "title": "Test Tacos",
    "emoji": "🌮",
    "method": "stovetop-oven",
    "servings_text": "4",
    "prep_text": "5 min",
    "cook_text": "15 min (stovetop)",
    "visibility": "public",
    "ingredients": [
        {"group": "Protein", "item": "Ground beef", "amount": "1 lb"},
        {"group": "Produce", "item": "Garlic, minced", "amount": "2 cloves"},
    ],
    "steps": ["**Brown** – Cook the beef."],
    "grocery": ["**Protein**: 1 lb ground beef"],
}


async def test_public_can_browse_and_preview_grocery_list():
    async with client_for() as c:
        recipes = (await c.get("/api/recipes")).json()
        assert len(recipes) == 38
        detail = (await c.get("/api/recipes/pasta-with-sausage-cream-sauce")).json()
        assert detail["ingredients"][1]["item"] == "Italian sausage links, sliced into coins"
        assert detail["can_edit"] is False
        md = (await c.get("/api/recipes/pasta-with-sausage-cream-sauce/markdown")).text
        assert md.startswith("## 🍝 Pasta with Sausage Cream Sauce")
        ld = (await c.get("/api/recipes/pasta-with-sausage-cream-sauce/jsonld")).json()
        assert ld["@type"] == "Recipe" and "1 lb Penne or rigatoni" in ld["recipeIngredient"]
        preview = (
            await c.post(
                "/api/grocery/preview",
                json={"recipe_slugs": ["pasta-with-sausage-cream-sauce", "garlic-butter-shrimp"]},
            )
        ).json()
        names = [i["name"] for a in preview["aisles"] for i in a["items"]]
        assert any("Garlic" in n for n in names)
        assert all(
            i["search_url"].startswith("https://www.amazon.com/s?k=")
            for a in preview["aisles"]
            for i in a["items"]
        )
        assert (await c.post("/api/recipes", json=NEW_RECIPE)).status_code == 401


async def test_pdf_renders():
    async with client_for() as c:
        r = await c.get(
            "/api/recipes/pdf?slugs=pasta-with-sausage-cream-sauce,garlic-butter-shrimp"
        )
        assert r.status_code == 200 and r.content[:4] == b"%PDF"


async def test_only_owners_publish_and_private_recipes_stay_private():
    owner = await get_user("owner@test.local")
    guest = await make_user("guest@test.local")
    async with client_for(guest) as c:
        r = await c.post("/api/recipes", json=NEW_RECIPE)
        assert r.status_code == 201
        mine = r.json()
        assert mine["visibility"] == "private"  # guests can't publish to the public cookbook
    async with client_for() as anon:
        assert (await anon.get(f"/api/recipes/{mine['slug']}")).status_code == 404
    async with client_for(owner) as c:
        assert (await c.get(f"/api/recipes/{mine['slug']}")).status_code == 404
        assert (await c.put(f"/api/recipes/{mine['id']}", json=NEW_RECIPE)).status_code == 404
        r = await c.post("/api/recipes", json=NEW_RECIPE)
        assert r.json()["visibility"] == "public" and r.json()["slug"] == "test-tacos-2"


async def test_copy_and_variants():
    guest = await make_user("guest@test.local")
    async with client_for(guest) as c:
        original = (await c.get("/api/recipes/pasta-with-sausage-cream-sauce")).json()
        copy = (await c.post(f"/api/recipes/{original['id']}/copy")).json()
        assert copy["parent"]["slug"] == original["slug"] and copy["can_edit"]
        again = (await c.get(f"/api/recipes/{original['slug']}")).json()
        assert [v["slug"] for v in again["variants"]] == [copy["slug"]]
    async with client_for() as anon:  # someone else's private copy isn't listed as a variant
        assert (await anon.get(f"/api/recipes/{original['slug']}")).json()["variants"] == []


async def test_shopping_list_rebuild_keeps_choices_and_builds_the_cart():
    user = await make_user("cook@test.local")
    async with client_for(user) as c:
        pasta = (await c.get("/api/recipes/pasta-with-sausage-cream-sauce")).json()
        shrimp = (await c.get("/api/recipes/garlic-butter-shrimp")).json()
        p = (
            await c.post(
                "/api/products",
                json={
                    "asin": "B0TESTSAUS",
                    "title": "365 Mild Italian Sausage Links, 1 lb",
                    "match_keys": ["Italian sausage links"],
                },
            )
        ).json()
        lst = (await c.post("/api/lists/current/recipes", json={"recipe_id": pasta["id"]})).json()
        items = {i["key"]: i for a in lst["aisles"] for i in a["items"]}
        assert items["italian sausage links"]["product"]["asin"] == "B0TESTSAUS"
        assert items["reserved"]["have"] is True  # pasta water
        garlic = items["garlic"]
        lst = (
            await c.patch(f"/api/lists/current/items/{garlic['id']}", json={"have": True})
        ).json()
        lst = (
            await c.post(
                "/api/lists/current/recipes", json={"recipe_id": shrimp["id"], "servings_factor": 2}
            )
        ).json()
        items = {i["key"]: i for a in lst["aisles"] for i in a["items"]}
        assert items["garlic"]["have"] is True and len(items["garlic"]["recipe_titles"]) == 2
        cart = (await c.get("/api/lists/current/cart")).json()
        assert cart["items"][0]["asin"] == "B0TESTSAUS"
        assert "#cookbook-cart=B0TESTSAUS%2A1" in cart["loader_url"]
        assert all(u["name"] != "Garlic, minced" for u in cart["unmatched"])
        lst = (await c.delete(f"/api/lists/current/recipes/{pasta['id']}")).json()
        keys = {i["key"] for a in lst["aisles"] for i in a["items"]}
        assert "italian sausage links" not in keys and "garlic" in keys


async def test_items_ticked_in_cart_leave_the_cart_manifest_and_survive_rebuilds():
    user = await make_user("cook@test.local")
    async with client_for(user) as c:
        pasta = (await c.get("/api/recipes/pasta-with-sausage-cream-sauce")).json()
        shrimp = (await c.get("/api/recipes/garlic-butter-shrimp")).json()
        await c.post(
            "/api/products",
            json={
                "asin": "B0TESTSAUS",
                "title": "Sausage links",
                "match_keys": ["Italian sausage links"],
            },
        )
        lst = (await c.post("/api/lists/current/recipes", json={"recipe_id": pasta["id"]})).json()
        sausage = next(
            i for a in lst["aisles"] for i in a["items"] if i["key"] == "italian sausage links"
        )
        assert sausage["in_cart"] is False and lst["counts"]["in_cart"] == 0
        assert [i["asin"] for i in lst["cart"]["items"]] == ["B0TESTSAUS"]

        lst = (
            await c.patch(f"/api/lists/current/items/{sausage['id']}", json={"in_cart": True})
        ).json()
        assert lst["counts"]["in_cart"] == 1 and lst["cart"]["items"] == []
        # Adding another recipe rebuilds the list; the tick stays.
        lst = (await c.post("/api/lists/current/recipes", json={"recipe_id": shrimp["id"]})).json()
        again = next(
            i for a in lst["aisles"] for i in a["items"] if i["key"] == "italian sausage links"
        )
        assert again["in_cart"] is True
        assert (await c.get("/api/lists/current/cart")).json()["items"] == []

        lst = (
            await c.patch(f"/api/lists/current/items/{sausage['id']}", json={"in_cart": False})
        ).json()
        assert [i["asin"] for i in lst["cart"]["items"]] == ["B0TESTSAUS"]


async def test_choosing_a_product_remembers_the_match():
    user = await make_user("cook@test.local")
    async with client_for(user) as c:
        pasta = (await c.get("/api/recipes/pasta-with-sausage-cream-sauce")).json()
        p = (
            await c.post(
                "/api/products", json={"asin": "B0TESTCREA", "title": "Heavy cream, 1 pint"}
            )
        ).json()
        lst = (await c.post("/api/lists/current/recipes", json={"recipe_id": pasta["id"]})).json()
        cream = next(i for a in lst["aisles"] for i in a["items"] if i["key"] == "heavy cream")
        await c.patch(f"/api/lists/current/items/{cream['id']}", json={"product_id": p["id"]})
        prods = (await c.get("/api/products?q=cream")).json()
        assert "heavy cream" in prods[0]["match_keys"]


async def test_purchase_history_is_idempotent_and_regulars_add():
    user = await make_user("cook@test.local")
    batch = {
        "purchases": [
            {
                "asin": "B09V3MS3F2",
                "title": "Honeydew Chunks Small",
                "ordered_on": "2026-11-01",
                "price_cents": 599,
            },
            {
                "asin": "B09V3MS3F2",
                "title": "Honeydew Chunks Small",
                "ordered_on": "2026-11-14",
                "price_cents": 649,
            },
        ]
    }
    async with client_for(user) as c:
        assert (await c.post("/api/products/purchases", json=batch)).json() == {
            "created": 1,
            "updated": 1,
        }
        await c.post("/api/products/purchases", json=batch)
        p = (await c.get("/api/products")).json()[0]
        assert (
            p["purchase_count"] == 2
            and p["price_cents"] == 649
            and p["last_purchased_on"] == "2026-11-14"
        )
        await c.patch(f"/api/products/{p['id']}", json={"is_regular": True, "regular_qty": 2})
        lst = (await c.post("/api/lists/current/regulars")).json()
        reg = next(i for a in lst["aisles"] for i in a["items"] if i["source"] == "regular")
        assert reg["quantity"] == 2
        assert lst["cart"]["items"][0]["quantity"] == 2


async def test_users_cannot_touch_each_others_data():
    a = await make_user("a@test.local")
    b = await make_user("b@test.local")
    async with client_for(a) as c:
        p = (await c.post("/api/products", json={"asin": "B0AAAAAAAA", "title": "A's"})).json()
    async with client_for(b) as c:
        assert (await c.get("/api/products")).json() == []
        assert (await c.patch(f"/api/products/{p['id']}", json={"title": "x"})).status_code == 404
        assert (await c.delete(f"/api/products/{p['id']}")).status_code == 404


async def test_password_login_and_cooklog():
    async with client_for() as c:
        r = await c.post(
            "/api/auth/login", json={"email": "owner@test.local", "password": "owner-password"}
        )
        assert r.status_code == 200 and r.json()["is_owner"] is True
        recipe = (await c.get("/api/recipes/garlic-butter-shrimp")).json()
        await c.post(
            "/api/cooklog",
            json={"recipe_id": recipe["id"], "rating": 5, "cooked_on": date.today().isoformat()},
        )
        log = (await c.get("/api/cooklog")).json()
        assert log[0]["slug"] == "garlic-butter-shrimp" and log[0]["rating"] == 5
        assert (await c.get("/api/recipes/garlic-butter-shrimp")).json()["cook_log"][0][
            "rating"
        ] == 5


async def test_api_keys_work_for_agents():
    user = await make_user("agent@test.local")
    async with client_for(user) as c:
        created = (await c.post("/api/me/api-keys", json={"name": "mac-mini"})).json()
    async with client_for() as c:
        r = await c.get("/api/lists/current/cart", headers={"X-API-Key": created["key"]})
        assert r.status_code == 200 and r.json()["items"] == []
        assert (
            await c.get("/api/lists/current/cart", headers={"X-API-Key": "ckb_nope"})
        ).status_code == 401


async def test_recipe_page_head_is_injected_for_public_recipes():
    from app.main import _recipe_head

    head = await _recipe_head("pasta-with-sausage-cream-sauce")
    assert '"@type": "Recipe"' in head and "<title>Pasta with Sausage Cream Sauce" in head
    assert await _recipe_head("no-such-recipe") is None


async def test_startup_seed_is_safe_with_several_workers():
    """uvicorn --workers 2 runs startup twice at once; the second must find the work done."""
    import asyncio

    from sqlalchemy import func, select, text

    from app.db.base import Base
    from app.db.session import AsyncSessionLocal, engine
    from app.models import Recipe
    from app.services.seed import run_startup_seed

    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.run_sync(Base.metadata.create_all)
    await asyncio.gather(run_startup_seed(), run_startup_seed(), run_startup_seed())
    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(func.count()).select_from(Recipe)) == 38


async def test_lines_pick_up_products_learned_later():
    user = await make_user("late@test.local")
    async with client_for(user) as c:
        pasta = (await c.get("/api/recipes/pasta-with-sausage-cream-sauce")).json()
        await c.post("/api/lists/current/recipes", json={"recipe_id": pasta["id"]})
        await c.post(
            "/api/products/purchases",
            json={
                "purchases": [
                    {
                        "asin": "B0BKM1W82J",
                        "title": "365 Organic Heavy Cream, 1 PT",
                        "ordered_on": "2026-11-14",
                        "match_keys": ["heavy cream"],
                    }
                ]
            },
        )
        lst = (await c.get("/api/lists/current")).json()
        cream = next(i for a in lst["aisles"] for i in a["items"] if i["key"] == "heavy cream")
        assert cream["product"]["asin"] == "B0BKM1W82J"
