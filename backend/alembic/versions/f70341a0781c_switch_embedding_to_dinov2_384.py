"""switch_embedding_to_dinov2_384

Revision ID: f70341a0781c
Revises: 004
Create Date: 2026-05-24 21:29:37.479764
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f70341a0781c'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 清空旧 512 维数据（均为 soft-deleted 测试数据），切换到 DINOv2 384 维
    op.execute("DELETE FROM embedding_vectors")
    op.execute("ALTER TABLE embedding_vectors ALTER COLUMN embedding TYPE vector(384)")
    op.alter_column('embedding_vectors', 'model_name',
                    existing_type=sa.VARCHAR(length=64),
                    server_default='dinov2_vits14',
                    existing_nullable=False)
    op.alter_column('embedding_vectors', 'dimension',
                    existing_type=sa.INTEGER(),
                    server_default='384',
                    existing_nullable=False)


def downgrade() -> None:
    op.execute("DELETE FROM embedding_vectors")
    op.execute("ALTER TABLE embedding_vectors ALTER COLUMN embedding TYPE vector(512)")
    op.alter_column('embedding_vectors', 'model_name',
                    existing_type=sa.VARCHAR(length=64),
                    server_default='resnet18',
                    existing_nullable=False)
    op.alter_column('embedding_vectors', 'dimension',
                    existing_type=sa.INTEGER(),
                    server_default='512',
                    existing_nullable=False)
