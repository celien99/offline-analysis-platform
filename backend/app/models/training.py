from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class TrainingRun(BaseModel):
    """记录每次训练执行的元数据，支撑自动重训练和增量训练的数据范围判定。"""

    __tablename__ = "training_runs"

    model_version_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    trigger: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="manual / auto_timer / auto_threshold"
    )
    train_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="full", comment="full / fine_tune"
    )
    reviewed_cluster_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_anomaly_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_anomaly_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="本次训练相比上次新增的 anomaly 数量"
    )
    metrics_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
