"""remove_region_partition_fields

移除旧版三分区 (region) 相关字段：
- anomaly_records: region_id
- clusters: region_id
- training_runs: region_id
- camera_configs: region_mode_enabled, region_upper/middle/lower_model_version_id

Revision ID: a91d7d2d925b
Revises: 9c0864a1f918
Create Date: 2026-05-29 08:28:50.468724
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a91d7d2d925b'
down_revision: Union[str, None] = '9c0864a1f918'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 移除 region_id 列及相关索引
    op.drop_index('ix_anomaly_records_region_id', table_name='anomaly_records')
    op.drop_column('anomaly_records', 'region_id')

    op.drop_index('ix_clusters_region_id', table_name='clusters')
    op.drop_column('clusters', 'region_id')

    op.drop_index('ix_training_runs_region_id', table_name='training_runs')
    op.drop_column('training_runs', 'region_id')

    # 移除 camera_configs 的三分区字段
    op.drop_column('camera_configs', 'region_lower_model_version_id')
    op.drop_column('camera_configs', 'region_middle_model_version_id')
    op.drop_column('camera_configs', 'region_upper_model_version_id')
    op.drop_column('camera_configs', 'region_mode_enabled')


def downgrade() -> None:
    # 恢复 camera_configs 三分区字段
    op.add_column('camera_configs', sa.Column(
        'region_mode_enabled', sa.Boolean(), nullable=False, server_default='0',
        comment='是否启用三分区模式'
    ))
    op.add_column('camera_configs', sa.Column(
        'region_upper_model_version_id', sa.String(length=32), nullable=True,
        comment='upper 区域 EfficientAD 模型版本 ID'
    ))
    op.add_column('camera_configs', sa.Column(
        'region_middle_model_version_id', sa.String(length=32), nullable=True,
        comment='middle 区域 EfficientAD 模型版本 ID'
    ))
    op.add_column('camera_configs', sa.Column(
        'region_lower_model_version_id', sa.String(length=32), nullable=True,
        comment='lower 区域 EfficientAD 模型版本 ID'
    ))
    op.create_foreign_key(None, 'camera_configs', 'model_versions', ['region_upper_model_version_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key(None, 'camera_configs', 'model_versions', ['region_middle_model_version_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key(None, 'camera_configs', 'model_versions', ['region_lower_model_version_id'], ['id'], ondelete='SET NULL')

    # 恢复 region_id 列
    op.add_column('training_runs', sa.Column(
        'region_id', sa.String(length=64), nullable=True,
        comment='训练数据隔离：ROI 区域 ID'
    ))
    op.create_index('ix_training_runs_region_id', 'training_runs', ['region_id'])

    op.add_column('clusters', sa.Column(
        'region_id', sa.String(length=64), nullable=True,
        comment='所属 ROI 区域 ID，用于区域级数据隔离'
    ))
    op.create_index('ix_clusters_region_id', 'clusters', ['region_id'])

    op.add_column('anomaly_records', sa.Column(
        'region_id', sa.String(length=64), nullable=True,
        comment='所属 ROI 区域 ID，用于细粒度数据隔离'
    ))
    op.create_index('ix_anomaly_records_region_id', 'anomaly_records', ['region_id'])
