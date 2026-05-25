from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class AnomalyRecord(BaseModel):
    __tablename__ = "anomaly_records"

    camera_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    seat_model_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True, comment="所属座椅型号 ID"
    )
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
        comment="pending / embedded / noise / clustered / reviewed"
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="单个异常被审核的时间（非 cluster 审核场景）"
    )
    anomaly_review_status: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
        comment="real_defect / false_alarm — 噪声异常审核结果"
    )
    decision_reason: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="在线检测的 decision_reason: texture_anomaly / filter_classifier_suppressed 等"
    )
    filter_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    filter_real_defect_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    filter_false_alarm_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    filter_class_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    filter_action: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
        comment="confirmed_ng / suppressed_to_ok / not_applied"
    )
    refined_crop_path: Mapped[str | None] = mapped_column(
        String(512), nullable=True,
        comment="经 mask refinement 处理后的裁剪图 MinIO 路径"
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
