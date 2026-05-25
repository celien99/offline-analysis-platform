"""Replace camera_config path columns with model_version_id FKs.

Revision ID: 008
Revises: 007
Create Date: 2026-05-25
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 删除旧的路径列
    op.drop_column("camera_configs", "patchcore_model_path")
    op.drop_column("camera_configs", "yolo_model_path")
    op.drop_column("camera_configs", "region_upper_model_path")
    op.drop_column("camera_configs", "region_middle_model_path")
    op.drop_column("camera_configs", "region_lower_model_path")

    # 添加 model_version_id 外键列
    op.add_column("camera_configs", sa.Column(
        "patchcore_model_version_id", sa.String(32),
        sa.ForeignKey("model_versions.id", ondelete="SET NULL"),
        nullable=True, comment="整体 PatchCore 模型版本 ID",
    ))
    op.add_column("camera_configs", sa.Column(
        "yolo_model_version_id", sa.String(32),
        sa.ForeignKey("model_versions.id", ondelete="SET NULL"),
        nullable=True, comment="YOLO 检测模型版本 ID",
    ))
    op.add_column("camera_configs", sa.Column(
        "region_upper_model_version_id", sa.String(32),
        sa.ForeignKey("model_versions.id", ondelete="SET NULL"),
        nullable=True, comment="upper 区域 PatchCore 模型版本 ID",
    ))
    op.add_column("camera_configs", sa.Column(
        "region_middle_model_version_id", sa.String(32),
        sa.ForeignKey("model_versions.id", ondelete="SET NULL"),
        nullable=True, comment="middle 区域 PatchCore 模型版本 ID",
    ))
    op.add_column("camera_configs", sa.Column(
        "region_lower_model_version_id", sa.String(32),
        sa.ForeignKey("model_versions.id", ondelete="SET NULL"),
        nullable=True, comment="lower 区域 PatchCore 模型版本 ID",
    ))


def downgrade() -> None:
    op.drop_column("camera_configs", "region_lower_model_version_id")
    op.drop_column("camera_configs", "region_middle_model_version_id")
    op.drop_column("camera_configs", "region_upper_model_version_id")
    op.drop_column("camera_configs", "yolo_model_version_id")
    op.drop_column("camera_configs", "patchcore_model_version_id")

    op.add_column("camera_configs", sa.Column(
        "region_lower_model_path", sa.String(512), nullable=True,
        comment="lower 区域 PatchCore 模型路径",
    ))
    op.add_column("camera_configs", sa.Column(
        "region_middle_model_path", sa.String(512), nullable=True,
        comment="middle 区域 PatchCore 模型路径",
    ))
    op.add_column("camera_configs", sa.Column(
        "region_upper_model_path", sa.String(512), nullable=True,
        comment="upper 区域 PatchCore 模型路径",
    ))
    op.add_column("camera_configs", sa.Column(
        "yolo_model_path", sa.String(512), nullable=False,
        comment="YOLO 检测模型路径",
    ))
    op.add_column("camera_configs", sa.Column(
        "patchcore_model_path", sa.String(512), nullable=False,
        comment="整体 PatchCore 模型路径",
    ))
