from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class ModelVersion(BaseModel):
    __tablename__ = "model_versions"

    model_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    model_type: Mapped[str] = mapped_column(
        String(32), nullable=False,
        comment="filter_classifier / embedding / yolo / patchcore"
    )
    framework: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pytorch"
    )
    artifact_path: Mapped[str] = mapped_column(String(512), nullable=False)
    metrics_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    parameters_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    mlflow_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="registered",
        comment="registered / validated / deployed / retired"
    )


class DeploymentRecord(BaseModel):
    __tablename__ = "deployment_records"

    model_version_id: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )
    target: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="production_line / camera_group"
    )
    deployed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    deployed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    previous_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    deployment_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active",
        comment="active / rolled_back / superseded"
    )
    rollback_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
