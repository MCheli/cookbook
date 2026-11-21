"""Structured outputs Claude fills in. Kept flat and simple so the JSON schema stays portable."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Method = Literal["instapot", "crockpot", "stovetop-oven", "other"]


class DraftIngredient(BaseModel):
    group: str = Field(
        description="Ingredient group, e.g. Protein, Vegetables, Sauce, Seasoning, Pantry, Dairy"
    )
    item: str = Field(
        description="What it is, with prep notes after a comma, e.g. 'Garlic, minced'"
    )
    amount: str = Field(
        description="Amount as a cook writes it, e.g. '1 lb', '½ cup', '3 cloves', 'to taste'"
    )


class RecipeDraft(BaseModel):
    title: str
    emoji: str = Field(description="One food emoji for the title")
    method: Method = Field(
        description="instapot, crockpot, stovetop-oven (stovetop, skillet, oven) or other"
    )
    description: str = Field(
        description="One or two plain sentences on what it is and why it's good"
    )
    servings_text: str = Field(description="e.g. '4' or '4–6'")
    prep_text: str = Field(description="e.g. '10 min'")
    cook_text: str = Field(description="e.g. '20 min (stovetop)' or '8 hr on LOW (4 hr on HIGH)'")
    tags: list[str] = Field(description="2–5 short lower-case tags, e.g. weeknight, spicy, chicken")
    ingredients: list[DraftIngredient]
    steps: list[str] = Field(
        description="Each step starts with a short bold label, like '**Brown Sausage** – Heat a skillet…'"
    )
    grocery: list[str] = Field(
        description="Shopping lines by aisle, like '**Protein**: 12 oz Italian sausage links'"
    )
    notes: str = Field(description="Tips, substitutions or storage notes; empty string if none")


class AdaptResult(BaseModel):
    recipe: RecipeDraft
    change_summary: list[str] = Field(
        description="Each change in a few words, e.g. 'Swapped heavy cream for half-and-half'"
    )
    variant_name: str = Field(
        description="Short name for this version, e.g. 'Spicier', 'No heavy cream', 'Serves 2'"
    )


class Idea(BaseModel):
    title: str
    emoji: str
    method: Method
    pitch: str = Field(description="One sentence: what it is and why it fits the request")
    existing_slug: str = Field(
        description="Slug of a matching recipe already in the cookbook, or empty string"
    )


class Ideas(BaseModel):
    ideas: list[Idea]


class WeekPick(BaseModel):
    slug: str
    reason: str


class WeekPlan(BaseModel):
    picks: list[WeekPick] = Field(description="Recipes from the cookbook for this week")
    new_idea: Idea = Field(description="One new recipe idea not yet in the cookbook")


class ProductMatch(BaseModel):
    item_key: str
    asin: str = Field(description="ASIN from the user's catalog, or empty string if none fits")
    confidence: Literal["high", "medium", "low"]
    reason: str


class ProductMatches(BaseModel):
    matches: list[ProductMatch]
