"""The markdown format, amounts, the grocery combiner and web import parsing (no database)."""

from __future__ import annotations

import pytest

from app.services.grocery import combine, ingredient_key
from app.services.quantities import add_amounts, parse_amount, scale_amount
from app.services.recipe_markdown import normalize, parse_markdown, to_markdown
from app.services.seed import bundled_recipes
from app.services.web_import import find_jsonld_recipe, jsonld_to_payload, split_ingredient


@pytest.mark.parametrize("entry", bundled_recipes(), ids=lambda e: e["file"])
def test_every_bundled_recipe_round_trips(entry):
    """Import then export gives back the original markdown (modulo whitespace)."""
    doc = parse_markdown(entry["markdown"])
    assert doc.title and doc.ingredients and doc.steps and doc.grocery
    assert normalize(to_markdown(doc)) == normalize(entry["markdown"])


def test_bundle_has_all_38_recipes_across_three_methods():
    entries = bundled_recipes()
    assert len(entries) == 38
    assert {e["method"] for e in entries} == {"instapot", "crockpot", "stovetop-oven"}


def test_title_emoji_is_split_off():
    doc = parse_markdown(
        "## 🍝 Pasta\n\n### Ingredients\n| Group | Item | Amount |\n|--|--|--|\n| **A** | b | 1 |\n\n### Method\n1. x\n"
    )
    assert (doc.emoji, doc.title) == ("🍝", "Pasta")


@pytest.mark.parametrize(
    ("text", "factor", "expected"),
    [
        ("1 lb", 1.5, "1½ lb"),
        ("½ cup", 2, "1 cup"),
        ("2–3 cloves", 2, "4–6 cloves"),
        ("to taste", 2, "to taste"),
        ("1 (15 oz) can", 2, "2 (15 oz) can"),
        ("12 oz", 0.5, "6 oz"),
    ],
)
def test_scale_amount(text, factor, expected):
    assert scale_amount(text, factor) == expected


def test_add_amounts_sums_compatible_units():
    assert add_amounts(["1 lb", "12 oz"]) == "1¾ lb"
    assert add_amounts(["½ cup", "2 Tbsp"]) == "⅝ cup"
    assert add_amounts(["3 cloves", "2 cloves", "to taste"]) == "5 cloves + to taste"
    assert parse_amount("a handful") is None


def test_ingredient_key_matches_the_original_site():
    assert ingredient_key("Garlic, minced") == "garlic"
    assert ingredient_key("Italian sausage links (mild or hot)") == "italian sausage links"


def test_combine_merges_across_recipes():
    class Ing:
        def __init__(self, group, item, amount):
            self.group_name, self.item, self.amount = group, item, amount

    class R:
        def __init__(self, title, ings):
            self.title, self.ingredients = title, ings

    a = R(
        "A",
        [Ing("Produce", "Garlic, minced", "3 cloves"), Ing("Protein", "Chicken thighs", "1 lb")],
    )
    b = R("B", [Ing("Vegetables", "Garlic", "2 cloves"), Ing("Pasta Water", "Reserved", "½ cup")])
    lines = {line.key: line for line in combine([(a, 1.0), (b, 2.0)])}
    assert lines["garlic"].amount_text == "7 cloves"
    assert lines["garlic"].recipe_titles == ["A", "B"]
    assert lines["reserved"].likely_on_hand


def test_jsonld_recipe_import():
    html = """<html><script type="application/ld+json">{"@context":"https://schema.org","@graph":[
      {"@type":"WebPage"},{"@type":"Recipe","name":"Test Chili","recipeYield":"6 servings",
      "prepTime":"PT15M","cookTime":"PT1H30M","recipeIngredient":["2 lbs ground beef","1 (15 oz) can black beans","Salt"],
      "recipeInstructions":[{"@type":"HowToStep","text":"Brown the beef."},{"@type":"HowToStep","text":"Simmer."}]}]}</script></html>"""
    node = find_jsonld_recipe(html)
    payload = jsonld_to_payload(node, "https://example.com/chili")
    assert payload["title"] == "Test Chili"
    assert payload["servings_text"] == "6"
    assert payload["prep_text"] == "15 min" and payload["cook_text"] == "1 hr 30 min"
    assert payload["ingredients"][0] == {
        "group": "Ingredients",
        "item": "ground beef",
        "amount": "2 lbs",
    }
    assert payload["ingredients"][1]["amount"] == "1 (15 oz) can"
    assert payload["ingredients"][2]["item"] == "Salt"
    assert payload["steps"] == ["Brown the beef.", "Simmer."]


def test_split_ingredient_keeps_unparseable_lines():
    assert split_ingredient("Salt and pepper to taste") == (None, "Salt and pepper to taste")
    assert split_ingredient("3 cloves garlic, minced") == ("3 cloves", "garlic, minced")
