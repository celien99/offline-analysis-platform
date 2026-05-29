from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TrainingConfig:
    model_type: str = "mobilenet_v3_small"
    num_classes: int = 2
    batch_size: int = 32
    epochs: int = 50
    learning_rate: float = 0.001
    image_size: tuple[int, int] = (224, 224)
    augmentations: bool = True
    validation_split: float = 0.2
    early_stopping_patience: int = 10
    target_metric: str = "val_accuracy"


@dataclass
class TrainingResult:
    run_id: str
    model_name: str
    model_version: str
    metrics: dict[str, float]
    artifact_path: str
    confusion_matrix: list[list[int]] | None = None
    class_names: list[str] = field(default_factory=lambda: ["real_defect", "false_alarm"])
    trained_at: datetime | None = None
    status: str = "registered"
    seat_model_id: str | None = None
    camera_id: str | None = None
