"""Add filter_classifier_model_version_id to camera_configs and seat_model_id to anomaly_records.

Revision ID: 009
Revises: 008
Create Date: 2026-05-25
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # camera_configs: 添加 filter_classifier_model_version_id
    op.add_column("camera_configs", sa.Column(
        "filter_classifier_model_version_id", sa.String(32),
        sa.ForeignKey("model_versions.id", ondelete="SET NULL"),
        nullable=True, comment="Filter Classifier 模型版本 ID",
    ))

    # anomaly_records: 添加 seat_model_id 用于分区聚类和追溯
    op.add_column("anomaly_records", sa.Column(
        "seat_model_id", sa.String(128), nullable=True, comment="所属座椅型号 ID",
    ))
    op.create_index(
        "ix_anomaly_records_seat_model_id",
        "anomaly_records",
        ["seat_model_id"],
    )

    # clusters: 添加 seat_model_id 用于按座椅型号隔离集群数据
    op.add_column("clusters", sa.Column(
        "seat_model_id", sa.String(128), nullable=True, comment="所属座椅型号 ID",
    ))
    op.create_index(
        "ix_clusters_seat_model_id",
        "clusters",
        ["seat_model_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_clusters_seat_model_id", table_name="clusters")
    op.drop_column("clusters", "seat_model_id")
    op.drop_index("ix_anomaly_records_seat_model_id", table_name="anomaly_records")
    op.drop_column("anomaly_records", "seat_model_id")
    op.drop_column("camera_configs", "filter_classifier_model_version_id")
