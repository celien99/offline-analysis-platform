"""Add gate_evaluations table for model deployment gating.

Revision ID: 011
Revises: 010
Create Date: 2026-05-26
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "011"
down_revision: str | None = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "gate_evaluations",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trace_id", sa.String(32), nullable=True),
        sa.Column("model_version_id", sa.String(32), nullable=False, index=True, comment="被评估的模型版本 ID"),
        sa.Column("status", sa.String(32), nullable=False, default="pending", comment="pending / passed / failed"),
        sa.Column("criteria_json", sa.Text, nullable=True, comment="评估时使用的门禁标准快照"),
        sa.Column("metrics_json", sa.Text, nullable=True, comment="整体评估指标"),
        sa.Column("stratified_metrics_json", sa.Text, nullable=True, comment="按型号/相机分层的评估指标"),
        sa.Column("baseline_metrics_json", sa.Text, nullable=True, comment="基线模型指标"),
        sa.Column("real_defect_recall", sa.Float, nullable=True, comment="真实缺陷召回率"),
        sa.Column("baseline_real_defect_recall", sa.Float, nullable=True, comment="基线模型真实缺陷召回率"),
        sa.Column("false_alarm_suppression_rate", sa.Float, nullable=True, comment="误报抑制率"),
        sa.Column("baseline_false_alarm_suppression_rate", sa.Float, nullable=True, comment="基线模型误报抑制率"),
        sa.Column("suppressed_real_defect_count", sa.Integer, nullable=True, comment="被模型错误抑制的真实缺陷数"),
        sa.Column("total_samples", sa.Integer, nullable=True, comment="评估集样本总数"),
        sa.Column("real_defect_samples", sa.Integer, nullable=True, comment="评估集真实缺陷样本数"),
        sa.Column("false_alarm_samples", sa.Integer, nullable=True, comment="评估集误报样本数"),
        sa.Column("failure_reasons_json", sa.Text, nullable=True, comment="失败的具体原因列表（JSON）"),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evaluated_by", sa.String(64), nullable=False, default="system:auto_gate", comment="评估触发者"),
    )
    op.create_index("ix_gate_evaluations_model_version_id", "gate_evaluations", ["model_version_id"], if_not_exists=True)


def downgrade() -> None:
    op.drop_index("ix_gate_evaluations_model_version_id", table_name="gate_evaluations")
    op.drop_table("gate_evaluations")
