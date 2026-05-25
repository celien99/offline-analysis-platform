"""Add training_runs, anomaly_reviews tables and anomaly_records feedback columns.

Revision ID: 005
Revises: f70341a0781c
Create Date: 2026-05-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: str | None = "f70341a0781c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 训练执行记录表
    op.create_table(
        "training_runs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("model_version_id", sa.String(32), nullable=False, index=True),
        sa.Column("trigger", sa.String(32), nullable=False,
                  comment="manual / auto_timer / auto_threshold"),
        sa.Column("train_type", sa.String(32), nullable=False, server_default="full",
                  comment="full / fine_tune"),
        sa.Column("reviewed_cluster_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_anomaly_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("new_anomaly_count", sa.Integer, nullable=False, server_default="0",
                  comment="本次训练相比上次新增的 anomaly 数"),
        sa.Column("metrics_json", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trace_id", sa.String(32), nullable=True),
    )

    # 异常审核记录表（噪声异常独立审核）
    op.create_table(
        "anomaly_reviews",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("anomaly_id", sa.String(32), nullable=False, index=True),
        sa.Column("reviewer", sa.String(64), nullable=False),
        sa.Column("action", sa.String(32), nullable=False,
                  comment="confirm_defect / mark_false_alarm"),
        sa.Column("defect_type", sa.String(64), nullable=True),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trace_id", sa.String(32), nullable=True),
    )

    # anomaly_records 新增字段
    op.add_column("anomaly_records", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("anomaly_records", sa.Column(
        "anomaly_review_status", sa.String(32), nullable=True,
        comment="real_defect / false_alarm"))
    op.add_column("anomaly_records", sa.Column(
        "decision_reason", sa.String(64), nullable=True,
        comment="在线检测决策原因"))
    op.add_column("anomaly_records", sa.Column("filter_confidence", sa.Float, nullable=True))
    op.add_column("anomaly_records", sa.Column("filter_real_defect_score", sa.Float, nullable=True))
    op.add_column("anomaly_records", sa.Column("filter_false_alarm_score", sa.Float, nullable=True))
    op.add_column("anomaly_records", sa.Column("filter_class_id", sa.Integer, nullable=True))
    op.add_column("anomaly_records", sa.Column(
        "filter_action", sa.String(32), nullable=True,
        comment="confirmed_ng / suppressed_to_ok / not_applied"))


def downgrade() -> None:
    op.drop_column("anomaly_records", "filter_action")
    op.drop_column("anomaly_records", "filter_class_id")
    op.drop_column("anomaly_records", "filter_false_alarm_score")
    op.drop_column("anomaly_records", "filter_real_defect_score")
    op.drop_column("anomaly_records", "filter_confidence")
    op.drop_column("anomaly_records", "decision_reason")
    op.drop_column("anomaly_records", "anomaly_review_status")
    op.drop_column("anomaly_records", "reviewed_at")
    op.drop_table("anomaly_reviews")
    op.drop_table("training_runs")
