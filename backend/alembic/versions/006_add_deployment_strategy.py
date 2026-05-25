"""Add deployment strategy columns.

Revision ID: 006
Revises: 005
Create Date: 2026-05-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "deployment_records",
        sa.Column(
            "strategy", sa.String(32), nullable=False, server_default="immediate",
            comment="immediate / shadow / canary",
        ),
    )
    op.add_column(
        "deployment_records",
        sa.Column("canary_promoted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "deployment_records",
        sa.Column(
            "canary_metrics_json", sa.Text, nullable=True,
            comment="金丝雀评估指标 JSON",
        ),
    )
    op.add_column(
        "deployment_records",
        sa.Column(
            "canary_status", sa.String(32), nullable=True,
            comment="pending_promotion / promoted / rolled_back_by_metrics",
        ),
    )


def downgrade() -> None:
    op.drop_column("deployment_records", "canary_status")
    op.drop_column("deployment_records", "canary_metrics_json")
    op.drop_column("deployment_records", "canary_promoted_at")
    op.drop_column("deployment_records", "strategy")
