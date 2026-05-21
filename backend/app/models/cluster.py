from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class Cluster(BaseModel):
    __tablename__ = "clusters"

    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    possible_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    representative_ids: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="JSON array of anomaly IDs"
    )
    centroid: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="JSON array of centroid embedding"
    )
    umap_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    umap_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    hdbscan_label: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)
    hdbscan_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending_review",
        comment="pending_review / reviewed / confirmed / ignored"
    )
    review_status: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
        comment="real_defect / false_alarm"
    )
    defect_type: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="wrinkle / scratch / reflection / stain / seam_shift"
    )
    reviewed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    clustering_run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    vlm_analysis_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    vlm_analyzed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ClusterMembership(BaseModel):
    __tablename__ = "cluster_memberships"

    cluster_id: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )
    anomaly_id: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )
    embedding_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    membership_score: Mapped[float | None] = mapped_column(Float, nullable=True)
