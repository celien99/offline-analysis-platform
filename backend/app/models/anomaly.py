from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text
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
    heatmap_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    crop_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    crop_paths: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="JSON 数组，存储所有异常裁剪图的 MinIO 路径"
    )
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True,
        comment="pending / embedded / clustered / reviewed"
    )

    @property
    def crop_path_list(self) -> list[str]:
        """返回所有 crop 路径列表。优先读 crop_paths JSON，回退到单字段 crop_path。"""
        if self.crop_paths:
            try:
                return json.loads(self.crop_paths)
            except (json.JSONDecodeError, TypeError):
                pass
        if self.crop_path:
            return [self.crop_path]
        return []
