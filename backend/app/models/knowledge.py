from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class KnowledgeEntry(BaseModel):
    __tablename__ = "knowledge_entries"

    cluster_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    category: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True,
        comment="defect / false_alarm / camera_issue / lighting / process"
    )
    defect_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    vlm_analysis_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    action: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ignore",
        comment="ignore / NG / review_required"
    )
    camera_ids: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="JSON array of camera IDs"
    )
    example_image_paths: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="JSON array of MinIO paths"
    )


class RuleEntry(BaseModel):
    __tablename__ = "rule_entries"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    rule_type: Mapped[str] = mapped_column(
        String(32), nullable=False,
        comment="ignore / flag / escalate"
    )
    condition_json: Mapped[str] = mapped_column(
        Text, nullable=False, comment="JSON rule condition"
    )
    priority: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    camera_ids: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="JSON array, null means all cameras"
    )
    knowledge_entry_id: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
