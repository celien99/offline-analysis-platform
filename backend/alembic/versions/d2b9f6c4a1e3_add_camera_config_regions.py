"""add_camera_config_regions

Revision ID: d2b9f6c4a1e3
Revises: acbb804f35ff
Create Date: 2026-06-02
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "d2b9f6c4a1e3"
down_revision: str | None = "acbb804f35ff"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "camera_config_regions",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trace_id", sa.String(length=32), nullable=True),
        sa.Column(
            "camera_config_id",
            sa.String(length=32),
            sa.ForeignKey("camera_configs.id", ondelete="CASCADE"),
            nullable=False,
            comment="所属 camera_configs.id",
        ),
        sa.Column("region_id", sa.String(length=64), nullable=False, comment="ROI 区域标识"),
        sa.Column("x1", sa.Float(), nullable=False, comment="归一化区域左上角 x"),
        sa.Column("y1", sa.Float(), nullable=False, comment="归一化区域左上角 y"),
        sa.Column("x2", sa.Float(), nullable=False, comment="归一化区域右下角 x"),
        sa.Column("y2", sa.Float(), nullable=False, comment="归一化区域右下角 y"),
        sa.Column(
            "patchcore_model_version_id",
            sa.String(length=32),
            sa.ForeignKey("model_versions.id", ondelete="CASCADE"),
            nullable=False,
            comment="该区域使用的 PatchCore 模型版本 ID",
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true(), comment="是否启用该区域"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0", comment="前端展示和配置生成顺序"),
        sa.Column("patchcore_overrides_json", sa.Text(), nullable=True, comment="区域级 PatchCore 配置覆盖 JSON"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("camera_config_id", "region_id", name="uq_camera_config_region"),
    )
    op.create_index("ix_camera_config_regions_camera_config_id", "camera_config_regions", ["camera_config_id"])


def downgrade() -> None:
    op.drop_index("ix_camera_config_regions_camera_config_id", table_name="camera_config_regions")
    op.drop_table("camera_config_regions")
