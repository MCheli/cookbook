"""Combine the ingredients of several recipes into one grocery list.

Same rules the original site used: an ingredient's key is its name in lower case without
parenthetical notes or anything after a comma, and lines are grouped by the recipe's
ingredient group in a fixed order. Amounts are added up where the units allow.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.quantities import add_amounts, scale_amount

AISLE_ORDER = [
    "Protein",
    "Vegetables",
    "Produce",
    "Dairy",
    "Grains",
    "Pantry",
    "Seasoning",
    "Spices",
    "Liquids",
    "Sauce",
    "Other",
]

# Wording that means "you already have this" for nearly everyone.
_ALWAYS_ON_HAND = {
    "water",
    "salt & pepper",
    "salt and pepper",
    "salt & black pepper",
    "salt and black pepper",
    "salt",
    "black pepper",
    "reserved",
    "ice",
}


def ingredient_key(name: str) -> str:
    key = name.lower()
    key = re.sub(r"\s*\(.*?\)\s*", " ", key)
    key = re.sub(r",.*$", "", key)
    key = re.sub(r"\s+", " ", key)
    return key.strip()


def search_term(name: str) -> str:
    term = re.sub(r"\s*\(.*?\)\s*", " ", name)
    term = re.sub(r",.*$", "", term)
    return re.sub(r"\s+", " ", term).strip()


def whole_foods_search_url(name: str) -> str:
    from urllib.parse import quote

    return f"https://www.amazon.com/s?k={quote(search_term(name))}&i=wholefoods"


def aisle_sort_key(aisle: str) -> tuple[int, str]:
    return (AISLE_ORDER.index(aisle) if aisle in AISLE_ORDER else len(AISLE_ORDER), aisle)


@dataclass
class GroceryLine:
    key: str
    name: str
    aisle: str
    amounts: list[str] = field(default_factory=list)
    recipe_titles: list[str] = field(default_factory=list)
    likely_on_hand: bool = False

    @property
    def amount_text(self) -> str:
        return add_amounts(self.amounts)


def combine(recipes: list[tuple[object, float]]) -> list[GroceryLine]:
    """`recipes` is [(recipe, servings_factor)]; each recipe has .title and .ingredients."""
    lines: dict[str, GroceryLine] = {}
    for recipe, factor in recipes:
        for ing in recipe.ingredients:
            key = ingredient_key(ing.item)
            if not key:
                continue
            aisle = ing.group_name or "Other"
            line = lines.get(key)
            if line is None:
                line = lines[key] = GroceryLine(
                    key=key,
                    name=ing.item,
                    aisle=aisle,
                    likely_on_hand=key in _ALWAYS_ON_HAND or "optional" in ing.item.lower(),
                )
            amount = scale_amount(ing.amount, factor)
            if amount:
                line.amounts.append(amount)
            if recipe.title not in line.recipe_titles:
                line.recipe_titles.append(recipe.title)
    return sorted(lines.values(), key=lambda g: (aisle_sort_key(g.aisle), g.name.lower()))
