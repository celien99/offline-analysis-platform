from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class EmbeddingVector(BaseModel):
    __tablename__ = "embedding_vectors"
    __table_args__ = (
        UniqueConstraint("anomaly_id", "embedding_type", name="uq_anomaly_embedding_type"),
    )

    anomaly_id: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )
    embedding_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="raw",
        comment="raw（原始 crop 提取）/ refined（精化 crop 提取），双轨对比"
    )
    embedding: Mapped[list[float]] = mapped_column(
        Vector(384), nullable=False
    )
    model_name: Mapped[str] = mapped_column(
        String(64), nullable=False, default="dinov2_vits14"
    )
    model_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False, default=384)
