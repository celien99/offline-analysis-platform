"""Add region_id / camera_id isolation columns to anomaly_records, clusters, training_runs.

Revision ID: 010
Revises: 009
Create Date: 2026-05-26
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "010"
down_revision: str | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # anomaly_records: 添加 region_id 用于区域级数据隔离
    op.add_column("anomaly_records", sa.Column(
        "region_id", sa.String(64), nullable=True, comment="所属 ROI 区域 ID",
    ))
    op.create_index(
        "ix_anomaly_records_region_id", "anomaly_records", ["region_id"],
    )

    # clusters: 添加 camera_id + region_id 用于多级数据隔离
    op.add_column("clusters", sa.Column(
        "camera_id", sa.String(64), nullable=True, comment="所属相机 ID",
    ))
    op.create_index("ix_clusters_camera_id", "clusters", ["camera_id"])
    op.add_column("clusters", sa.Column(
        "region_id", sa.String(64), nullable=True, comment="所属 ROI 区域 ID",
    ))
    op.create_index("ix_clusters_region_id", "clusters", ["region_id"])

    # training_runs: 添加 seat_model_id + camera_id + region_id 用于训练数据隔离追溯
    op.add_column("training_runs", sa.Column(
        "seat_model_id", sa.String(128), nullable=True, comment="训练数据隔离：座椅型号 ID",
    ))
    op.create_index("ix_training_runs_seat_model_id", "training_runs", ["seat_model_id"])
    op.add_column("training_runs", sa.Column(
        "camera_id", sa.String(64), nullable=True, comment="训练数据隔离：相机 ID",
    ))
    op.create_index("ix_training_runs_camera_id", "training_runs", ["camera_id"])
    op.add_column("training_runs", sa.Column(
        "region_id", sa.String(64), nullable=True, comment="训练数据隔离：ROI 区域 ID",
    ))
    op.create_index("ix_training_runs_region_id", "training_runs", ["region_id"])


def downgrade() -> None:
    # training_runs
    op.drop_index("ix_training_runs_region_id", table_name="training_runs")
    op.drop_column("training_runs", "region_id")
    op.drop_index("ix_training_runs_camera_id", table_name="training_runs")
    op.drop_column("training_runs", "camera_id")
    op.drop_index("ix_training_runs_seat_model_id", table_name="training_runs")
    op.drop_column("training_runs", "seat_model_id")

    # clusters
    op.drop_index("ix_clusters_region_id", table_name="clusters")
    op.drop_column("clusters", "region_id")
    op.drop_index("ix_clusters_camera_id", table_name="clusters")
    op.drop_column("clusters", "camera_id")

    # anomaly_records
    op.drop_index("ix_anomaly_records_region_id", table_name="anomaly_records")
    op.drop_column("anomaly_records", "region_id")
