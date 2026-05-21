from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class EmbeddingVector(BaseModel):
    __tablename__ = "embedding_vectors"

    anomaly_id: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True, unique=True
    )
    embedding: Mapped[list[float]] = mapped_column(
        Vector(512), nullable=False
    )
    model_name: Mapped[str] = mapped_column(
        String(64), nullable=False, default="resnet18"
    )
    model_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False, default=512)
