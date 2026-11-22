"""ORM models. Every user-owned row carries user_id/owner_id; queries always filter on it."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _uuid_pk() -> Mapped[UUID]:
    return mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


def _user_fk(**kw) -> Mapped[UUID]:
    return mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, **kw
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255))
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True)
    display_name: Mapped[str | None] = mapped_column(String(255))
    # Bring your own key: Fernet-encrypted with COOKBOOK_SECRETS_KEY; never sent back out.
    anthropic_key_enc: Mapped[str | None] = mapped_column(Text)
    anthropic_key_last4: Mapped[str | None] = mapped_column(String(8))
    # Food profile used in AI prompts: {"likes": str, "dislikes": str, "notes": str}
    preferences: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[UUID] = _uuid_pk()
    user_id: Mapped[UUID] = _user_fk(index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()

    KEY_PREFIX = "ckb_"

    @staticmethod
    def generate_key() -> str:
        return f"{ApiKey.KEY_PREFIX}{secrets.token_urlsafe(32)}"

    @staticmethod
    def hash_key(raw: str) -> str:
        from app.config import settings

        return hmac.new(settings.API_KEY_PEPPER.encode(), raw.encode(), hashlib.sha256).hexdigest()


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[UUID] = _uuid_pk()
    owner_id: Mapped[UUID] = _user_fk(index=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    emoji: Mapped[str | None] = mapped_column(String(16))
    # instapot | crockpot | stovetop-oven | other (see services/recipes.METHODS)
    method: Mapped[str] = mapped_column(String(32), nullable=False, default="stovetop-oven")
    description: Mapped[str | None] = mapped_column(Text)
    servings_text: Mapped[str | None] = mapped_column(String(60))
    prep_text: Mapped[str | None] = mapped_column(String(120))
    cook_text: Mapped[str | None] = mapped_column(String(160))
    servings_base: Mapped[float | None] = mapped_column(Float)
    prep_minutes: Mapped[int | None] = mapped_column(Integer)
    cook_minutes: Mapped[int | None] = mapped_column(Integer)
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String(40)), nullable=False, default=list, server_default="{}"
    )
    visibility: Mapped[str] = mapped_column(String(16), nullable=False, default="private")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="published")
    # original | ai | import | remix | manual
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
    source_url: Mapped[str | None] = mapped_column(Text)
    parent_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("recipes.id", ondelete="SET NULL"), index=True
    )
    # For AI-made recipes: {"model", "prompt", "created_at"}; shown on the page.
    ai_meta: Mapped[dict | None] = mapped_column(JSONB)
    notes: Mapped[str | None] = mapped_column(Text)
    # The markdown a recipe was imported from, kept verbatim for provenance.
    source_markdown: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    ingredients: Mapped[list[RecipeIngredient]] = relationship(
        order_by="RecipeIngredient.position", cascade="all, delete-orphan", lazy="selectin"
    )
    steps: Mapped[list[RecipeStep]] = relationship(
        order_by="RecipeStep.position", cascade="all, delete-orphan", lazy="selectin"
    )
    grocery: Mapped[list[RecipeGroceryLine]] = relationship(
        order_by="RecipeGroceryLine.position", cascade="all, delete-orphan", lazy="selectin"
    )


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    id: Mapped[UUID] = _uuid_pk()
    recipe_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("recipes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    group_name: Mapped[str | None] = mapped_column(String(80))
    item: Mapped[str] = mapped_column(String(240), nullable=False)
    amount: Mapped[str | None] = mapped_column(String(80))


class RecipeStep(Base):
    __tablename__ = "recipe_steps"

    id: Mapped[UUID] = _uuid_pk()
    recipe_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("recipes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)  # inline markdown (**bold**, *italic*)


class RecipeGroceryLine(Base):
    __tablename__ = "recipe_grocery_lines"

    id: Mapped[UUID] = _uuid_pk()
    recipe_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("recipes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)


class SavedRecipe(Base):
    __tablename__ = "saved_recipes"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    recipe_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("recipes.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = _created()


class Product(Base):
    """A Whole Foods product (by ASIN) in one user's catalog, matched to ingredient keys."""

    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("user_id", "asin", name="uq_products_user_asin"),
        Index("ix_products_match_keys", "match_keys", postgresql_using="gin"),
    )

    id: Mapped[UUID] = _uuid_pk()
    user_id: Mapped[UUID] = _user_fk(index=True)
    asin: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(400), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(120))
    size_text: Mapped[str | None] = mapped_column(String(80))
    price_cents: Mapped[int | None] = mapped_column(Integer)
    sold_by_weight: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    match_keys: Mapped[list[str]] = mapped_column(
        ARRAY(String(120)), nullable=False, default=list, server_default="{}"
    )
    is_regular: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    regular_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    purchase_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Distinct order dates, so re-sending the same order history doesn't double count.
    purchase_dates: Mapped[list[date]] = mapped_column(
        ARRAY(Date), nullable=False, default=list, server_default="{}"
    )
    last_purchased_on: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ShoppingList(Base):
    __tablename__ = "shopping_lists"

    id: Mapped[UUID] = _uuid_pk()
    user_id: Mapped[UUID] = _user_fk(index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active"
    )  # active|ordered
    created_at: Mapped[datetime] = _created()
    ordered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    recipes: Mapped[list[ShoppingListRecipe]] = relationship(
        order_by="ShoppingListRecipe.position", cascade="all, delete-orphan", lazy="selectin"
    )
    items: Mapped[list[ShoppingListItem]] = relationship(
        order_by="ShoppingListItem.position", cascade="all, delete-orphan", lazy="selectin"
    )


class ShoppingListRecipe(Base):
    __tablename__ = "shopping_list_recipes"
    __table_args__ = (UniqueConstraint("list_id", "recipe_id", name="uq_list_recipe"),)

    id: Mapped[UUID] = _uuid_pk()
    list_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("shopping_lists.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recipe_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False
    )
    servings_factor: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ShoppingListItem(Base):
    """One line of a list. Recipe lines are rebuilt from the recipes; the user's choices
    (have it, product, quantity, in the cart) survive the rebuild because they are keyed by `key`.
    """

    __tablename__ = "shopping_list_items"
    __table_args__ = (UniqueConstraint("list_id", "key", name="uq_list_item_key"),)

    id: Mapped[UUID] = _uuid_pk()
    list_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("shopping_lists.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    aisle: Mapped[str] = mapped_column(String(80), nullable=False, default="Other")
    amount_text: Mapped[str | None] = mapped_column(String(240))
    recipe_titles: Mapped[list[str]] = mapped_column(
        ARRAY(String(200)), nullable=False, default=list, server_default="{}"
    )
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, default="recipe"
    )  # recipe|regular|manual
    have: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    product_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL")
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Ticked once the cook has put it in the Whole Foods cart (the Add button on the list).
    in_cart: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )


class CookLog(Base):
    __tablename__ = "cook_logs"

    id: Mapped[UUID] = _uuid_pk()
    user_id: Mapped[UUID] = _user_fk(index=True)
    recipe_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("recipes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    cooked_on: Mapped[date] = mapped_column(Date, nullable=False)
    rating: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()


class ChatThread(Base):
    __tablename__ = "chat_threads"

    id: Mapped[UUID] = _uuid_pk()
    user_id: Mapped[UUID] = _user_fk(index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="New chat")
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    messages: Mapped[list[ChatMessage]] = relationship(
        order_by="ChatMessage.created_at", cascade="all, delete-orphan", lazy="selectin"
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[UUID] = _uuid_pk()
    thread_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("chat_threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user | assistant
    # Anthropic content blocks as sent/received, so a thread can be replayed to the model.
    content: Mapped[list] = mapped_column(JSONB, nullable=False)
    # What the UI shows: {"text": str, "actions": [...]} (tool results rendered as cards).
    display: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.clock_timestamp()
    )


class AiUsage(Base):
    __tablename__ = "ai_usage"

    id: Mapped[UUID] = _uuid_pk()
    user_id: Mapped[UUID] = _user_fk(index=True)
    purpose: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(60), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = _created()


class SiteState(Base):
    __tablename__ = "site_state"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
