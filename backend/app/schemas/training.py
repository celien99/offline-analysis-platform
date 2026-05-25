from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TrainingStartRequest(BaseModel):
    model_type: str = Field(
        default="mobilenet_v3_small",
        pattern=r"^(mobilenet_v3_small|efficientnet_b0|resnet18)$",
    )
    num_classes: int = Field(default=2, ge=2, le=10)
    batch_size: int = Field(default=32, ge=1, le=256)
    epochs: int = Field(default=50, ge=1, le=500)
    learning_rate: float = Field(default=0.001, gt=0.0, le=0.1)
    validation_split: float = Field(default=0.2, gt=0.0, lt=1.0)
    class_names: list[str] = Field(
        default_factory=lambda: ["real_defect", "false_alarm"]
    )
    augmentations: bool = True
    anomaly_ids: list[str] | None = None


class MetricTrainingStartRequest(BaseModel):
    backbone_type: str = Field(
        default="mobilenet_v3_small",
        pattern=r"^(mobilenet_v3_small|efficientnet_b0|resnet18)$",
    )
    embedding_size: int = Field(default=256, ge=64, le=1024)
    loss_type: str = Field(default="arcface", pattern=r"^(arcface|triplet)$")
    batch_size: int = Field(default=32, ge=1, le=256)
    epochs: int = Field(default=50, ge=1, le=500)
    learning_rate: float = Field(default=0.001, gt=0.0, le=0.1)
    validation_split: float = Field(default=0.2, gt=0.0, lt=1.0)
    anomaly_ids: list[str] | None = None


class TrainingStatusResponse(BaseModel):
    task_id: str
    status: str
    model_name: str | None = None
    model_version: str | None = None
    progress: float | None = Field(default=None, ge=0.0, le=1.0)
    current_epoch: int | None = None
    total_epochs: int | None = None
    metrics: dict[str, float] | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
