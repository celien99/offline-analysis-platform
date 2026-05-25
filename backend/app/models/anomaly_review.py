from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class AnomalyReview(BaseModel):
    """记录对单个异常（非 cluster 归属）的审核操作，用于噪声样本审核场景。"""

    __tablename__ = "anomaly_reviews"

    anomaly_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    reviewer: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="confirm_defect / mark_false_alarm"
    )
    defect_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
