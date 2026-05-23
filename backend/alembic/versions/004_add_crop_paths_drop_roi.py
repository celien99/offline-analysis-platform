"""Add crop_paths JSON column, drop roi_path.

Revision ID: 004
Revises: 003
Create Date: 2026-05-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "anomaly_records",
        sa.Column("crop_paths", sa.Text(), nullable=True),
    )
    op.drop_column("anomaly_records", "roi_path")


def downgrade() -> None:
    op.add_column(
        "anomaly_records",
        sa.Column("roi_path", sa.String(512), nullable=True),
    )
    op.drop_column("anomaly_records", "crop_paths")
