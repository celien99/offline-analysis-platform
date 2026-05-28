"""move_yolo_to_seat_model_add_calibration

Revision ID: 9c0864a1f918
Revises: 00e1f667111b
Create Date: 2026-05-28 17:28:33.958845
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c0864a1f918'
down_revision: Union[str, None] = '00e1f667111b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 将 YOLO 模型从 camera_configs 提升到 seat_models（全局共享）
    op.add_column('seat_models', sa.Column('yolo_model_version_id', sa.String(length=32), nullable=True, comment='全局 YOLO 检测模型版本 ID'))
    op.create_foreign_key(None, 'seat_models', 'model_versions', ['yolo_model_version_id'], ['id'], ondelete='SET NULL')

    # 2. seat_models 新增全局校准模型引用
    op.add_column('seat_models', sa.Column('projector_model_version_id', sa.String(length=32), nullable=True, comment='全局 EmbeddingProjector 模型版本 ID'))
    op.create_foreign_key(None, 'seat_models', 'model_versions', ['projector_model_version_id'], ['id'], ondelete='SET NULL')
    op.add_column('seat_models', sa.Column('whitening_matrix_model_version_id', sa.String(length=32), nullable=True, comment='全局 WhiteningTransform 模型版本 ID'))
    op.create_foreign_key(None, 'seat_models', 'model_versions', ['whitening_matrix_model_version_id'], ['id'], ondelete='SET NULL')

    # 3. 从 camera_configs 移除 yolo_model_version_id（已提升到 seat_models）
    op.drop_constraint(op.f('camera_configs_yolo_model_version_id_fkey'), 'camera_configs', type_='foreignkey')
    op.drop_column('camera_configs', 'yolo_model_version_id')


def downgrade() -> None:
    # 1. 恢复 camera_configs 的 yolo_model_version_id
    op.add_column('camera_configs', sa.Column('yolo_model_version_id', sa.VARCHAR(length=32), autoincrement=False, nullable=True, comment='YOLO 检测模型版本 ID'))
    op.create_foreign_key(op.f('camera_configs_yolo_model_version_id_fkey'), 'camera_configs', 'model_versions', ['yolo_model_version_id'], ['id'], ondelete='SET NULL')

    # 2. 移除 seat_models 的校准模型 FK 和列
    op.drop_constraint(None, 'seat_models', type_='foreignkey')
    op.drop_column('seat_models', 'whitening_matrix_model_version_id')
    op.drop_constraint(None, 'seat_models', type_='foreignkey')
    op.drop_column('seat_models', 'projector_model_version_id')

    # 3. 移除 seat_models 的 YOLO FK 和列
    op.drop_constraint(None, 'seat_models', type_='foreignkey')
    op.drop_column('seat_models', 'yolo_model_version_id')
