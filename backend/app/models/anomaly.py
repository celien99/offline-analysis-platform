from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class AnomalyRecord(BaseModel):
    __tablename__ = "anomaly_records"

    camera_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="patchcore / filter_classifier / rule_engine"
    )
    anomaly_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    date_folder: Mapped[str] = mapped_column(String(16), nullable=False, comment="YYYY-MM-DD")
    original_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    roi_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    heatmap_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    crop_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True,
        comment="pending / embedded / clustered / reviewed"
    )
