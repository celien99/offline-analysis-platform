"""Add seat_models and camera_configs tables.

Revision ID: 007
Revises: 510d1b30d73b
Create Date: 2026-05-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: str | None = "510d1b30d73b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "seat_models",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "seat_model_id", sa.String(128), unique=True, nullable=False, index=True,
            comment="座椅型号标识符",
        ),
        sa.Column(
            "display_name", sa.String(256), nullable=False,
            comment="前端显示名称",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trace_id", sa.String(32), nullable=True),
    )

    op.create_table(
        "camera_configs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "camera_id", sa.String(128), nullable=False,
            comment="相机标识符",
        ),
        sa.Column(
            "seat_model_id", sa.String(128),
            sa.ForeignKey("seat_models.seat_model_id", ondelete="CASCADE"),
            nullable=False, index=True, comment="所属座椅型号 seat_model_id",
        ),
        sa.Column(
            "patchcore_model_path", sa.String(512), nullable=False,
            comment="整体 PatchCore 模型路径",
        ),
        sa.Column(
            "yolo_model_path", sa.String(512), nullable=False,
            comment="YOLO 检测模型路径",
        ),
        sa.Column(
            "detection_confidence", sa.Float, nullable=False, server_default="0.25",
            comment="YOLO 置信度阈值",
        ),
        sa.Column(
            "patchcore_image_size", sa.Integer, nullable=False, server_default="256",
            comment="PatchCore 输入图像尺寸",
        ),
        sa.Column(
            "patchcore_threshold", sa.Float, nullable=False, server_default="0.99",
            comment="PatchCore 异常阈值分位数",
        ),
        sa.Column(
            "region_mode_enabled", sa.Boolean, nullable=False, server_default="0",
            comment="是否启用三分区模式",
        ),
        sa.Column(
            "region_upper_model_path", sa.String(512), nullable=True,
            comment="upper 区域 PatchCore 模型路径",
        ),
        sa.Column(
            "region_middle_model_path", sa.String(512), nullable=True,
            comment="middle 区域 PatchCore 模型路径",
        ),
        sa.Column(
            "region_lower_model_path", sa.String(512), nullable=True,
            comment="lower 区域 PatchCore 模型路径",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trace_id", sa.String(32), nullable=True),
        sa.UniqueConstraint("seat_model_id", "camera_id", name="uq_seat_camera"),
    )


def downgrade() -> None:
    op.drop_table("camera_configs")
    op.drop_table("seat_models")
