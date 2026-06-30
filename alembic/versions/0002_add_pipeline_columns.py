"""add pipeline processing columns

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-30

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("page_count", sa.Integer(), nullable=True))
    op.add_column("documents", sa.Column("lang", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("bbox_data", JSONB(), nullable=True))
    op.add_column("documents", sa.Column("error_detail", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "error_detail")
    op.drop_column("documents", "bbox_data")
    op.drop_column("documents", "lang")
    op.drop_column("documents", "page_count")
