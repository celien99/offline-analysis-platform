"""Add embedding_type column for dual-track raw/refined embedding comparison.

Revision ID: 012
Revises: 011
Create Date: 2026-05-26
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "012"
down_revision: str | None = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 添加 embedding_type 列（raw / refined）
    op.add_column("embedding_vectors", sa.Column(
        "embedding_type", sa.String(16), nullable=False,
        server_default="raw",
        comment="raw（原始 crop）/ refined（精化 crop），双轨对比",
    ))
    # 移除旧的 unique constraint on anomaly_id
    op.drop_constraint(
        "embedding_vectors_anomaly_id_key", "embedding_vectors",
        type_="unique",
    )
    op.drop_index("ix_embedding_vectors_anomaly_id", table_name="embedding_vectors")
    # 重建 index + 新的 composite unique constraint
    op.create_index(
        "ix_embedding_vectors_anomaly_id", "embedding_vectors", ["anomaly_id"],
    )
    op.create_unique_constraint(
        "uq_anomaly_embedding_type", "embedding_vectors",
        ["anomaly_id", "embedding_type"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_anomaly_embedding_type", "embedding_vectors", type_="unique")
    op.drop_index("ix_embedding_vectors_anomaly_id", table_name="embedding_vectors")
    op.create_index(
        "ix_embedding_vectors_anomaly_id", "embedding_vectors", ["anomaly_id"],
        unique=True,
    )
    op.drop_column("embedding_vectors", "embedding_type")
