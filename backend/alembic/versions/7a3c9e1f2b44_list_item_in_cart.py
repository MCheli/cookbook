"""List items remember whether they're already in the Whole Foods cart.

Revision ID: 7a3c9e1f2b44
Revises: 52c9064242d1
Create Date: 2026-11-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7a3c9e1f2b44"
down_revision: str | None = "52c9064242d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "shopping_list_items",
        sa.Column("in_cart", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("shopping_list_items", "in_cart")
