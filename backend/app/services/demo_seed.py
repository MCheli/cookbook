"""The public demo's data: Claudius Banks, a made-up cook, laid out backwards from today.

Run on every demo start (entrypoint: `--drop`, `alembic upgrade head`, then seed); the server restarts the demo
nightly so dates stay current. Deterministic per day. Refuses to run outside demo mode or against a
database holding anyone but demo personas.
"""

from __future__ import annotations

import asyncio
import random
import sys
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import text

from app.config import settings
from app.db.session import AsyncSessionLocal, engine
from app.models import (
    AiUsage,
    ChatMessage,
    ChatThread,
    CookLog,
    Product,
    Recipe,
    ShoppingList,
    ShoppingListRecipe,
    User,
)
from app.schemas import RecipeIn
from app.services import lists as lists_svc
from app.services.recipes import apply_payload, unique_slug
from app.services.seed import bundled_recipes, import_markdown_recipe

MODEL = "claude-sonnet-5-5"

# name, size, cents, match keys, regular qty (0 = not a regular)
PRODUCTS = [
    (
        "365 by Whole Foods Market, Boneless Skinless Chicken Thighs",
        "about 1.5 lb",
        899,
        ["boneless chicken thighs", "chicken thighs", "boneless skinless chicken thighs"],
        0,
    ),
    (
        "365 by Whole Foods Market, Boneless Skinless Chicken Breasts",
        "about 1.5 lb",
        999,
        ["chicken breast", "boneless chicken breasts", "chicken breasts"],
        0,
    ),
    (
        "365 by Whole Foods Market, Mild Italian Pork Sausage Links",
        "1 lb",
        599,
        ["italian sausage links", "italian sausage"],
        0,
    ),
    (
        "365 by Whole Foods Market, 85% Lean Ground Beef",
        "1 lb",
        699,
        ["ground beef", "lean ground beef"],
        0,
    ),
    (
        "Whole Foods Market, Wild Raw Shrimp, Peeled & Deveined",
        "1 lb",
        1299,
        ["shrimp", "large shrimp"],
        0,
    ),
    (
        "Whole Foods Market, Atlantic Salmon Fillet",
        "about 1 lb",
        1399,
        ["salmon fillets", "salmon"],
        0,
    ),
    (
        "365 by Whole Foods Market, Organic Penne Rigate",
        "16 oz",
        199,
        ["penne or rigatoni", "penne", "rigatoni"],
        0,
    ),
    (
        "365 by Whole Foods Market, Long Grain White Rice",
        "32 oz",
        349,
        ["long grain rice", "white rice", "rice"],
        0,
    ),
    ("365 by Whole Foods Market, Heavy Whipping Cream", "1 pint", 449, ["heavy cream"], 0),
    (
        "365 by Whole Foods Market, Parmesan Cheese, Grated",
        "8 oz",
        499,
        ["parmesan cheese", "parmesan"],
        0,
    ),
    (
        "365 by Whole Foods Market, Shredded Mexican Blend",
        "8 oz",
        399,
        ["shredded mexican cheese", "shredded cheese", "cheddar cheese"],
        0,
    ),
    ("365 by Whole Foods Market, Organic Crushed Tomatoes", "28 oz", 249, ["crushed tomatoes"], 0),
    (
        "365 by Whole Foods Market, Organic Chicken Broth",
        "32 fl oz",
        299,
        ["chicken broth", "low-sodium chicken broth"],
        0,
    ),
    ("365 by Whole Foods Market, Unsalted Butter", "16 oz", 529, ["butter", "unsalted butter"], 0),
    ("Organic Garlic", "3 count", 199, ["garlic", "garlic cloves"], 0),
    ("Organic Yellow Onion", "1 each", 129, ["yellow onion", "onion"], 0),
    (
        "Organic Red Bell Pepper",
        "1 each",
        199,
        ["red bell pepper", "bell pepper", "bell peppers"],
        0,
    ),
    ("Organic Broccoli Crowns", "about 1 lb", 299, ["broccoli florets", "broccoli"], 0),
    ("Organic Limes", "2 count", 149, ["lime juice", "limes", "lime"], 0),
    (
        "365 by Whole Foods Market, Flour Tortillas, Burrito Size",
        "8 count",
        349,
        ["flour tortillas", "tortillas"],
        0,
    ),
    ("365 by Whole Foods Market, Organic Salsa Verde", "16 oz", 349, ["salsa verde"], 0),
    ("Nature's Own Thick Sliced White Bread", "22 oz", 399, ["bread", "thick white bread"], 0),
    (
        "365 by Whole Foods Market, Frozen Mixed Vegetables",
        "16 oz",
        199,
        ["frozen mixed vegetables"],
        0,
    ),
    ("Mother-in-Law's Gochujang", "10 oz", 699, ["gochujang"], 0),
    ("365 by Whole Foods Market, Organic Honey", "12 oz", 599, ["honey"], 0),
    ("365 by Whole Foods Market, Honeydew Chunks", "16 oz", 599, [], 1),
    ("Earthbound Farm Veggie Tray with Ranch", "1 each", 899, [], 1),
    ("365 by Whole Foods Market, Caesar Salad Kit", "10 oz", 399, [], 1),
    ("Siete Sea Salt Grain-Free Tortilla Chips", "5 oz", 449, [], 1),
    ("Sparkling Water, Lime", "8 × 12 fl oz", 499, [], 2),
]

VARIANTS = [
    (
        "pasta-with-sausage-cream-sauce",
        "make it spicier",
        {
            "title": "Spicy Sausage Cream Sauce Pasta",
            "emoji": "🌶️",
            "swap": {
                "Italian sausage links, sliced into coins": (
                    "Hot Italian sausage links, sliced into coins",
                    "12 oz",
                ),
                "Red pepper flakes": ("Red pepper flakes", "1 tsp"),
            },
            "add": [("Finish", "Calabrian chili paste", "1 Tbsp")],
            "summary": [
                "Hot sausage instead of mild",
                "Doubled the red pepper flakes",
                "Calabrian chili to finish",
            ],
        },
    ),
    (
        "instant-pot-butter-chicken",
        "make it for two",
        {
            "title": "Instant Pot Butter Chicken for Two",
            "emoji": "🍛",
            "factor": 0.5,
            "summary": ["Halved every amount", "Same pressure time"],
        },
    ),
    (
        "classic-ground-beef-tacos",
        "turkey instead of beef",
        {
            "title": "Ground Turkey Tacos",
            "emoji": "🌮",
            "swap": {"Ground beef": ("Ground turkey", "1 lb")},
            "add": [("Seasoning", "Smoked paprika", "1 tsp")],
            "summary": ["Ground turkey instead of beef", "Smoked paprika for depth"],
        },
    ),
]

AI_RECIPES = [
    (
        "weeknight chicken with gochujang, one pan",
        RecipeIn(
            title="Sheet-Pan Gochujang Chicken Thighs",
            emoji="🔥",
            method="stovetop-oven",
            description="Sticky, spicy-sweet thighs and broccoli roasted on one pan.",
            servings_text="4",
            prep_text="10 min",
            cook_text="25 min (oven at 425°F)",
            tags=["chicken", "spicy", "weeknight"],
            ingredients=[
                {"group": "Protein", "item": "Boneless chicken thighs", "amount": "2 lb"},
                {"group": "Vegetables", "item": "Broccoli florets", "amount": "1 lb"},
                {"group": "Sauce", "item": "Gochujang", "amount": "3 Tbsp"},
                {"group": "Sauce", "item": "Honey", "amount": "2 Tbsp"},
                {"group": "Sauce", "item": "Soy sauce", "amount": "1 Tbsp"},
                {"group": "Sauce", "item": "Garlic, minced", "amount": "3 cloves"},
                {"group": "Finish", "item": "Sesame seeds", "amount": "1 tsp"},
            ],
            steps=[
                "**Heat** – Heat the oven to 425°F and line a sheet pan.",
                "**Coat** – Whisk gochujang, honey, soy sauce and garlic; toss with the chicken and broccoli.",
                "**Roast** – Spread out and roast 22–25 min, until the chicken reaches 165°F and the edges char.",
                "**Finish** – Spoon the pan sauce over and scatter sesame seeds.",
            ],
            grocery=[
                "**Protein**: 2 lb boneless chicken thighs",
                "**Produce**: broccoli, garlic",
                "**Pantry**: gochujang, honey, soy sauce, sesame seeds",
            ],
            visibility="private",
            status="published",
            source="ai",
        ),
    ),
    (
        "something cozy with orzo and lemon, one pot",
        RecipeIn(
            title="One-Pot Lemon Chicken Orzo",
            emoji="🍋",
            method="stovetop-oven",
            description="Creamy without cream: orzo cooked in broth with chicken, lemon and parmesan.",
            servings_text="4",
            prep_text="10 min",
            cook_text="25 min (one pot)",
            tags=["chicken", "one-pot", "weeknight"],
            ingredients=[
                {"group": "Protein", "item": "Chicken breast, cubed", "amount": "1 lb"},
                {"group": "Pasta", "item": "Orzo", "amount": "1½ cups"},
                {"group": "Liquids", "item": "Chicken broth", "amount": "4 cups"},
                {"group": "Vegetables", "item": "Baby spinach", "amount": "3 cups"},
                {"group": "Finish", "item": "Lemon, zested and juiced", "amount": "1"},
                {"group": "Finish", "item": "Parmesan cheese, grated", "amount": "½ cup"},
            ],
            steps=[
                "**Brown** – Brown the chicken in olive oil, 5 min.",
                "**Simmer** – Add orzo and broth; simmer 10–12 min, stirring often.",
                "**Wilt** – Stir in spinach until wilted.",
                "**Finish** – Off the heat, add lemon and parmesan; season to taste.",
            ],
            grocery=[
                "**Protein**: 1 lb chicken breast",
                "**Pasta**: orzo",
                "**Produce**: spinach, 1 lemon",
                "**Dairy**: parmesan",
            ],
            visibility="private",
            status="draft",
            source="ai",
        ),
    ),
]


async def _drop_schema() -> None:
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))


def _asin(n: int) -> str:
    return f"B0DEMO{n:04d}"


async def seed() -> None:
    from app.demo import check_demo_database

    rng = random.Random(20261121)
    today = date.today()
    async with AsyncSessionLocal() as db:
        await check_demo_database(db)
        persona = User(
            email=settings.DEMO_USER_EMAIL,
            display_name="Claudius Banks",
            preferences={
                "likes": "Bold flavors, spicy food, one-pot and dump-and-go dinners",
                "dislikes": "Mushrooms",
                "notes": "Cooks for two; leftovers go to lunch.",
            },
        )
        db.add(persona)
        await db.flush()

        recipes: dict[str, Recipe] = {}
        for entry in bundled_recipes():
            r = await import_markdown_recipe(
                db,
                persona,
                entry["markdown"],
                entry["method"],
                source="original",
                visibility="public",
            )
            recipes[r.slug] = r

        for slug, prompt, spec in VARIANTS:
            base = recipes[slug]
            ingredients = []
            for i in base.ingredients:
                item, amount = spec.get("swap", {}).get(i.item, (i.item, i.amount))
                if spec.get("factor"):
                    from app.services.quantities import scale_amount

                    amount = scale_amount(amount, spec["factor"])
                ingredients.append({"group": i.group_name, "item": item, "amount": amount})
            ingredients += [
                {"group": g, "item": it, "amount": a} for g, it, a in spec.get("add", [])
            ]
            data = RecipeIn(
                title=spec["title"],
                emoji=spec["emoji"],
                method=base.method,
                servings_text=("2" if spec.get("factor") else base.servings_text),
                prep_text=base.prep_text,
                cook_text=base.cook_text,
                ingredients=ingredients,
                steps=[s.text for s in base.steps],
                grocery=[g.text for g in base.grocery],
                notes="Changes: " + "; ".join(spec["summary"]) + ".",
                visibility="public",
                source="remix",
                parent_id=base.id,
                ai_meta={
                    "model": MODEL,
                    "prompt": prompt,
                    "created_at": datetime.now(UTC).isoformat(),
                },
            )
            v = Recipe(
                owner_id=persona.id,
                slug=await unique_slug(db, data.title),
                source="remix",
                parent_id=base.id,
                ai_meta=data.ai_meta,
            )
            apply_payload(v, data, persona)
            db.add(v)
            await db.flush()
            recipes[v.slug] = v

        for prompt, data in AI_RECIPES:
            data.ai_meta = {
                "model": MODEL,
                "prompt": prompt,
                "created_at": datetime.now(UTC).isoformat(),
            }
            r = Recipe(
                owner_id=persona.id,
                slug=await unique_slug(db, data.title),
                source="ai",
                ai_meta=data.ai_meta,
            )
            apply_payload(r, data, persona)
            db.add(r)
            await db.flush()
            recipes[r.slug] = r

        products = []
        for n, (title, size, cents, keys, regular) in enumerate(PRODUCTS, 1):
            dates = sorted(
                {
                    today - timedelta(days=7 * w + 2)
                    for w in range(10)
                    if rng.random() < (0.9 if regular else 0.35)
                }
            )
            p = Product(
                user_id=persona.id,
                asin=_asin(n),
                title=title,
                size_text=size,
                price_cents=cents,
                sold_by_weight="about" in size,
                match_keys=keys,
                is_regular=bool(regular),
                regular_qty=max(regular, 1),
                purchase_dates=dates,
                purchase_count=len(dates),
                last_purchased_on=dates[-1] if dates else None,
                source="history",
                notes=(
                    "Pack weights vary; one pack usually covers 1½ lb." if "about" in size else None
                ),
            )
            db.add(p)
            products.append(p)
        await db.flush()

        # Six past weeks: two recipes ordered, cooked over the following days, rated.
        rotation = [
            "instant-pot-jerk-chicken-rice",
            "pasta-with-sausage-cream-sauce",
            "classic-ground-beef-tacos",
            "garlic-butter-shrimp",
            "chicken-quesadillas",
            "grilled-cheese-with-tomato-soup",
            "crock-pot-honey-garlic-chicken",
            "korean-gochujang-beef-bowls",
            "sheet-pan-gochujang-chicken-thighs",
            "instant-pot-butter-chicken",
            "teriyaki-salmon-bowls",
            "salsa-verde-chicken-skillet",
        ]
        rotation = [s for s in rotation if s in recipes]
        for week in range(6, 0, -1):
            ordered = datetime.combine(
                today - timedelta(days=7 * week + 1), datetime.min.time(), tzinfo=UTC
            ).replace(hour=15)
            picks = rotation[(6 - week) * 2 : (6 - week) * 2 + 2]
            lst = ShoppingList(
                user_id=persona.id,
                title=f"Week of {ordered:%b} {ordered.day}",
                status="ordered",
                ordered_at=ordered,
                recipes=[
                    ShoppingListRecipe(recipe_id=recipes[s].id, position=i)
                    for i, s in enumerate(picks)
                ],
                items=[],
            )
            db.add(lst)
            await db.flush()
            await lists_svc.rebuild(db, lst, persona)
            for i, s in enumerate(picks):
                db.add(
                    CookLog(
                        user_id=persona.id,
                        recipe_id=recipes[s].id,
                        cooked_on=(ordered + timedelta(days=1 + i * 2)).date(),
                        rating=rng.choice([4, 5, 5, 3, 4]),
                        notes=rng.choice(
                            [
                                None,
                                "Doubled the garlic.",
                                "Great leftovers.",
                                "Needed more salt.",
                                None,
                            ]
                        ),
                    )
                )

        this_week = ["one-pan-lemon-herb-chicken-potatoes", "spicy-sausage-cream-sauce-pasta"]
        current = ShoppingList(
            user_id=persona.id,
            title=f"Week of {today:%b} {today.day}",
            status="active",
            items=[],
            recipes=[
                ShoppingListRecipe(recipe_id=recipes[s].id, position=i)
                for i, s in enumerate(this_week)
                if s in recipes
            ],
        )
        db.add(current)
        await db.flush()
        await lists_svc.rebuild(db, current, persona)
        await lists_svc.add_regulars(db, current, persona)
        for item in current.items:
            if item.aisle in ("Seasoning", "Spices") or item.key in (
                "olive oil",
                "salt & black pepper",
            ):
                item.have = True

        thread = ChatThread(
            user_id=persona.id, title="Something spicy with the sausage", messages=[]
        )
        db.add(thread)
        await db.flush()
        convo = [
            (
                "user",
                "I have sausage left. Can you make the sausage pasta spicier and put it on this week's list?",
                [],
            ),
            (
                "assistant",
                "Done. I saved **Spicy Sausage Cream Sauce Pasta**, a version of your sausage pasta with hot links, "
                "double the chili flakes and Calabrian chili to finish, and added it to this week's list.",
                [
                    {
                        "type": "draft",
                        "slug": "spicy-sausage-cream-sauce-pasta",
                        "title": "Spicy Sausage Cream Sauce Pasta",
                        "emoji": "🌶️",
                        "based_on": "Pasta with Sausage Cream Sauce",
                    },
                    {
                        "type": "list",
                        "message": "Added Spicy Sausage Cream Sauce Pasta to this week's list",
                    },
                ],
            ),
            ("user", "What can I swap for heavy cream if I'm out?", []),
            (
                "assistant",
                "Half-and-half works (simmer gently so it doesn't split), or whole milk plus 2 Tbsp butter. "
                "For this recipe I'd use 1 cup half-and-half and add the parmesan off the heat.",
                [],
            ),
        ]
        for role, msg, actions in convo:
            db.add(
                ChatMessage(
                    thread_id=thread.id,
                    role=role,
                    content=[{"type": "text", "text": msg}],
                    display=(
                        {"text": msg, "actions": actions} if role == "assistant" else {"text": msg}
                    ),
                )
            )
            await db.flush()

        for days_ago, purpose, inp, out in [
            (1, "chat", 6200, 640),
            (3, "adapt", 2100, 1400),
            (5, "generate", 1800, 2300),
            (8, "suggest_week", 3900, 500),
            (12, "chat", 5100, 420),
        ]:
            db.add(
                AiUsage(
                    user_id=persona.id,
                    purpose=purpose,
                    model=MODEL,
                    input_tokens=inp,
                    output_tokens=out,
                    created_at=datetime.now(UTC) - timedelta(days=days_ago),
                )
            )
        await db.commit()


async def main(drop: bool) -> None:
    """`--drop` empties the database (the entrypoint then migrates); no flag seeds it."""
    if not settings.DEMO_MODE:
        raise SystemExit("demo_seed runs only with COOKBOOK_DEMO_MODE=true")
    from app.demo import check_demo_database

    if drop:
        async with AsyncSessionLocal() as db:
            try:
                await check_demo_database(db)
            except RuntimeError:
                raise
            except Exception:  # noqa: BLE001 — a brand-new database has no tables yet
                pass
        await _drop_schema()
    else:
        await seed()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main(drop="--drop" in sys.argv))
