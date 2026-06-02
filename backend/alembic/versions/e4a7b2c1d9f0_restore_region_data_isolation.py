"""restore_region_data_isolation

Revision ID: e4a7b2c1d9f0
Revises: d2b9f6c4a1e3
Create Date: 2026-06-02
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "e4a7b2c1d9f0"
down_revision: str | None = "d2b9f6c4a1e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "anomaly_records",
        sa.Column(
            "region_id",
            sa.String(length=64),
            nullable=True,
            comment="所属 ROI 区域 ID，用于区域级 PatchCore 数据隔离",
        ),
    )
    op.create_index("ix_anomaly_records_region_id", "anomaly_records", ["region_id"])

    op.add_column(
        "embedding_vectors",
        sa.Column(
            "region_id",
            sa.String(length=64),
            nullable=True,
            comment="所属 ROI 区域 ID，冗余自 anomaly_records 便于向量检索隔离",
        ),
    )
    op.create_index("ix_embedding_vectors_region_id", "embedding_vectors", ["region_id"])
    op.execute("""
        UPDATE embedding_vectors AS ev
        SET region_id = ar.region_id
        FROM anomaly_records AS ar
        WHERE ev.anomaly_id = ar.id
          AND ev.deleted_at IS NULL
          AND ar.deleted_at IS NULL
          AND ar.region_id IS NOT NULL
    """)

    op.add_column(
        "clusters",
        sa.Column(
            "region_id",
            sa.String(length=64),
            nullable=True,
            comment="所属 ROI 区域 ID，用于区域级聚类隔离",
        ),
    )
    op.create_index("ix_clusters_region_id", "clusters", ["region_id"])


def downgrade() -> None:
    op.drop_index("ix_clusters_region_id", table_name="clusters")
    op.drop_column("clusters", "region_id")

    op.drop_index("ix_embedding_vectors_region_id", table_name="embedding_vectors")
    op.drop_column("embedding_vectors", "region_id")

    op.drop_index("ix_anomaly_records_region_id", table_name="anomaly_records")
    op.drop_column("anomaly_records", "region_id")
