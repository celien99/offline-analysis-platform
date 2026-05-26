"""rename patchcore columns to efficientad in camera_configs

Revision ID: 00e1f667111b
Revises: 012
Create Date: 2026-05-26 15:30:58.643911
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '00e1f667111b'
down_revision: Union[str, None] = '012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """将 camera_configs 表的 patchcore_* 列重命名为 efficientad_*"""
    op.alter_column("camera_configs", "patchcore_model_version_id", new_column_name="efficientad_model_version_id")
    op.alter_column("camera_configs", "patchcore_image_size", new_column_name="efficientad_image_size")
    op.alter_column("camera_configs", "patchcore_threshold", new_column_name="efficientad_threshold")


def downgrade() -> None:
    """回退：efficientad_* → patchcore_*"""
    op.alter_column("camera_configs", "efficientad_model_version_id", new_column_name="patchcore_model_version_id")
    op.alter_column("camera_configs", "efficientad_image_size", new_column_name="patchcore_image_size")
    op.alter_column("camera_configs", "efficientad_threshold", new_column_name="patchcore_threshold")
