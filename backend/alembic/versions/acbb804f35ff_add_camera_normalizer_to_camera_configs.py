"""add_camera_normalizer_to_camera_configs

为 camera_configs 表添加 normalizer_model_version_id 列，
支持每机位绑定独立的 CameraNormalizer stats 文件。

Revision ID: acbb804f35ff
Revises: a91d7d2d925b
Create Date: 2026-05-29 08:59:28.703296
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'acbb804f35ff'
down_revision: Union[str, None] = 'a91d7d2d925b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('camera_configs', sa.Column(
        'normalizer_model_version_id', sa.String(length=32), nullable=True,
        comment='CameraNormalizer stats 模型版本 ID (per-camera mean/std .npz)',
    ))
    op.create_foreign_key(
        'fk_camera_configs_normalizer_model_version',
        'camera_configs', 'model_versions',
        ['normalizer_model_version_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint(
        'fk_camera_configs_normalizer_model_version',
        'camera_configs',
        type_='foreignkey',
    )
    op.drop_column('camera_configs', 'normalizer_model_version_id')
