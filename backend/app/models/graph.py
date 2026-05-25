from __future__ import annotations

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class SimilarityEdge(BaseModel):
    """预计算的 KNN 相似度图的边"""

    __tablename__ = "similarity_edges"

    source_anomaly_id: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True, comment="源异常ID"
    )
    target_anomaly_id: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True, comment="目标异常ID"
    )
    embedding_id: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="源 embedding ID"
    )
    rank: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="KNN 中的排名 (1 = 最近邻)"
    )
    similarity_score: Mapped[float] = mapped_column(
        Float, nullable=False, comment="余弦相似度 (0-1, 越高越相似)"
    )


class GraphBuildRecord(BaseModel):
    """图谱构建记录 — 追踪何时构建/重建"""

    __tablename__ = "graph_build_records"

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="running",
        comment="running / completed / failed"
    )
    total_anomalies: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_edges: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    k_neighbors: Mapped[int] = mapped_column(
        Integer, nullable=False, default=10, comment="每个节点的 K 近邻数"
    )
    error_message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    started_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    completed_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
