"""将 embedding_vectors 的唯一索引改为部分索引，排除已软删除行。

Revision ID: 003
Revises: 002
Create Date: 2026-05-23
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. 删除旧的全局唯一索引
    op.execute("DROP INDEX IF EXISTS ix_embedding_vectors_anomaly_id")
    # 2. 创建部分唯一索引：仅对未软删除的行生效
    op.execute(
        "CREATE UNIQUE INDEX ix_embedding_vectors_anomaly_id "
        "ON embedding_vectors (anomaly_id) WHERE deleted_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_embedding_vectors_anomaly_id")
    op.execute(
        "CREATE UNIQUE INDEX ix_embedding_vectors_anomaly_id "
        "ON embedding_vectors (anomaly_id)"
    )
