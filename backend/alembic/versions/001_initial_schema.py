"""Initial schema — all core tables with pgvector extension.

Revision ID: 001
Revises:
Create Date: 2026-05-20
"""

from __future__ import annotations

from collections.abc import Sequence

import pgvector
import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "anomaly_records",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("camera_id", sa.String(64), nullable=False, index=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("anomaly_score", sa.Float, nullable=True),
        sa.Column("date_folder", sa.String(16), nullable=False),
        sa.Column("original_path", sa.String(512), nullable=True),
        sa.Column("roi_path", sa.String(512), nullable=True),
        sa.Column("heatmap_path", sa.String(512), nullable=True),
        sa.Column("crop_path", sa.String(512), nullable=True),
        sa.Column("metadata_json", sa.Text, nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending", index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trace_id", sa.String(32), nullable=True),
    )

    op.create_table(
        "embedding_vectors",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("anomaly_id", sa.String(32), nullable=False, index=True, unique=True),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(512), nullable=False),
        sa.Column("model_name", sa.String(64), nullable=False, server_default="resnet18"),
        sa.Column("model_version", sa.String(32), nullable=True),
        sa.Column("dimension", sa.Integer, nullable=False, server_default="512"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trace_id", sa.String(32), nullable=True),
    )
    op.create_index(
        "ix_embedding_vectors_embedding",
        "embedding_vectors",
        ["embedding"],
        postgresql_using="ivfflat",
        postgresql_with={"lists": 100},
    )

    op.create_table(
        "clusters",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(128), nullable=True),
        sa.Column("sample_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("possible_type", sa.String(64), nullable=True),
        sa.Column("representative_ids", sa.Text, nullable=True),
        sa.Column("centroid", sa.Text, nullable=True),
        sa.Column("umap_x", sa.Float, nullable=True),
        sa.Column("umap_y", sa.Float, nullable=True),
        sa.Column("hdbscan_label", sa.Integer, nullable=False, server_default="-1"),
        sa.Column("hdbscan_probability", sa.Float, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending_review"),
        sa.Column("review_status", sa.String(32), nullable=True),
        sa.Column("defect_type", sa.String(64), nullable=True),
        sa.Column("reviewed_by", sa.String(64), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clustering_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trace_id", sa.String(32), nullable=True),
    )

    op.create_table(
        "cluster_memberships",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("cluster_id", sa.String(32), nullable=False, index=True),
        sa.Column("anomaly_id", sa.String(32), nullable=False, index=True),
        sa.Column("embedding_id", sa.String(32), nullable=True),
        sa.Column("membership_score", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trace_id", sa.String(32), nullable=True),
    )

    op.create_table(
        "review_records",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("cluster_id", sa.String(32), nullable=False, index=True),
        sa.Column("reviewer", sa.String(64), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("defect_type", sa.String(64), nullable=True),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("previous_status", sa.String(32), nullable=True),
        sa.Column("new_status", sa.String(32), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trace_id", sa.String(32), nullable=True),
    )

    op.create_table(
        "model_versions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("model_name", sa.String(128), nullable=False, index=True),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("model_type", sa.String(32), nullable=False),
        sa.Column("framework", sa.String(32), nullable=False, server_default="pytorch"),
        sa.Column("artifact_path", sa.String(512), nullable=False),
        sa.Column("metrics_json", sa.Text, nullable=True),
        sa.Column("parameters_json", sa.Text, nullable=True),
        sa.Column("mlflow_run_id", sa.String(64), nullable=True),
        sa.Column("trained_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="registered"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trace_id", sa.String(32), nullable=True),
    )

    op.create_table(
        "deployment_records",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("model_version_id", sa.String(32), nullable=False, index=True),
        sa.Column("target", sa.String(64), nullable=False),
        sa.Column("deployed_by", sa.String(64), nullable=True),
        sa.Column("deployed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("previous_version", sa.String(32), nullable=True),
        sa.Column("deployment_status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("rollback_reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trace_id", sa.String(32), nullable=True),
    )

    op.create_table(
        "knowledge_entries",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("cluster_id", sa.String(32), nullable=True, index=True),
        sa.Column("category", sa.String(64), nullable=False, index=True),
        sa.Column("defect_type", sa.String(64), nullable=True),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("vlm_analysis_json", sa.Text, nullable=True),
        sa.Column("action", sa.String(32), nullable=False, server_default="ignore"),
        sa.Column("camera_ids", sa.Text, nullable=True),
        sa.Column("example_image_paths", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trace_id", sa.String(32), nullable=True),
    )

    op.create_table(
        "rule_entries",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("rule_type", sa.String(32), nullable=False),
        sa.Column("condition_json", sa.Text, nullable=False),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("camera_ids", sa.Text, nullable=True),
        sa.Column("knowledge_entry_id", sa.String(32), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trace_id", sa.String(32), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("rule_entries")
    op.drop_table("knowledge_entries")
    op.drop_table("deployment_records")
    op.drop_table("model_versions")
    op.drop_table("review_records")
    op.drop_table("cluster_memberships")
    op.drop_table("clusters")
    op.drop_table("embedding_vectors")
    op.drop_table("anomaly_records")
    op.execute("DROP EXTENSION IF EXISTS vector")
