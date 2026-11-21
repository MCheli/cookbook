"""Request and response bodies."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Method = Literal["instapot", "crockpot", "stovetop-oven", "other"]


class UserOut(BaseModel):
    id: UUID
    email: str
    display_name: str | None
    is_owner: bool
    has_anthropic_key: bool
    anthropic_key_last4: str | None
    preferences: dict


class LoginRequest(BaseModel):
    email: str
    password: str


class IngredientIn(BaseModel):
    group: str | None = Field(default=None, max_length=80)
    item: str = Field(min_length=1, max_length=240)
    amount: str | None = Field(default=None, max_length=80)


class RecipeIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    emoji: str | None = Field(default=None, max_length=16)
    method: Method = "stovetop-oven"
    description: str | None = Field(default=None, max_length=2000)
    servings_text: str | None = Field(default=None, max_length=60)
    prep_text: str | None = Field(default=None, max_length=120)
    cook_text: str | None = Field(default=None, max_length=160)
    tags: list[str] = Field(default_factory=list, max_length=20)
    visibility: Literal["public", "private"] = "private"
    status: Literal["published", "draft"] = "published"
    notes: str | None = Field(default=None, max_length=4000)
    ingredients: list[IngredientIn] = Field(default_factory=list, max_length=80)
    steps: list[str] = Field(default_factory=list, max_length=60)
    grocery: list[str] = Field(default_factory=list, max_length=40)
    parent_id: UUID | None = None
    source: Literal["manual", "ai", "import", "remix", "original"] = "manual"
    source_url: str | None = Field(default=None, max_length=2000)
    ai_meta: dict | None = None


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    key_prefix: str
    is_active: bool
    last_used_at: datetime | None
    created_at: datetime


class ApiKeyCreated(ApiKeyOut):
    key: str


class AnthropicKeyIn(BaseModel):
    key: str = Field(min_length=20, max_length=400)


class PreferencesIn(BaseModel):
    likes: str | None = Field(default=None, max_length=1000)
    dislikes: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=2000)
    default_servings_factor: float | None = Field(default=None, ge=0.25, le=8)


class GroceryPreviewIn(BaseModel):
    recipe_slugs: list[str] = Field(min_length=1, max_length=20)
    factors: dict[str, float] = Field(default_factory=dict)


class ListRecipeIn(BaseModel):
    recipe_id: UUID
    servings_factor: float = Field(default=1.0, ge=0.25, le=8)


class ListRecipePatch(BaseModel):
    servings_factor: float = Field(ge=0.25, le=8)


class ListItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    amount_text: str | None = Field(default=None, max_length=240)
    aisle: str | None = Field(default=None, max_length=80)
    product_id: UUID | None = None
    quantity: int = Field(default=1, ge=1, le=50)


class ListItemPatch(BaseModel):
    have: bool | None = None
    product_id: UUID | None = None
    clear_product: bool = False
    quantity: int | None = Field(default=None, ge=1, le=50)
    remember_match: bool = True  # also add this item's key to the product's match keys


class ProductIn(BaseModel):
    asin: str = Field(pattern=r"^[A-Z0-9]{10}$")
    title: str = Field(min_length=1, max_length=400)
    brand: str | None = Field(default=None, max_length=120)
    size_text: str | None = Field(default=None, max_length=80)
    price_cents: int | None = Field(default=None, ge=0, le=10_000_00)
    sold_by_weight: bool = False
    notes: str | None = Field(default=None, max_length=2000)
    match_keys: list[str] = Field(default_factory=list, max_length=30)
    is_regular: bool = False
    regular_qty: int = Field(default=1, ge=1, le=50)


class ProductPatch(BaseModel):
    title: str | None = Field(default=None, max_length=400)
    brand: str | None = Field(default=None, max_length=120)
    size_text: str | None = Field(default=None, max_length=80)
    price_cents: int | None = Field(default=None, ge=0, le=10_000_00)
    sold_by_weight: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)
    match_keys: list[str] | None = Field(default=None, max_length=30)
    is_regular: bool | None = None
    regular_qty: int | None = Field(default=None, ge=1, le=50)


class PurchaseIn(BaseModel):
    """One line of a past Whole Foods order, as an agent reads it from the order page."""

    asin: str = Field(pattern=r"^[A-Z0-9]{10}$")
    title: str = Field(min_length=1, max_length=400)
    ordered_on: date
    quantity: int = Field(default=1, ge=1, le=100)
    price_cents: int | None = Field(default=None, ge=0, le=10_000_00)
    size_text: str | None = Field(default=None, max_length=80)
    match_keys: list[str] = Field(default_factory=list, max_length=30)


class PurchasesIn(BaseModel):
    purchases: list[PurchaseIn] = Field(min_length=1, max_length=1000)


class CookLogIn(BaseModel):
    recipe_id: UUID
    cooked_on: date | None = None
    rating: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = Field(default=None, max_length=2000)
