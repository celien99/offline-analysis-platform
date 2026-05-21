"""Add VLM analysis fields to clusters.

Revision ID: 002
Revises: 001
Create Date: 2026-05-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "clusters",
        sa.Column("vlm_analysis_json", sa.Text(), nullable=True),
    )
    op.add_column(
        "clusters",
        sa.Column("vlm_analyzed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("clusters", "vlm_analyzed_at")
    op.drop_column("clusters", "vlm_analysis_json")
