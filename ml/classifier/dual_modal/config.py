from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DualModalConfig:
    """Configuration for DualModalFilter training."""
    # Model
    num_classes: int = 2
    image_size: int = 448
    feature_dropout_rate: float = 0.2

    # Training
    learning_rate: float = 1e-4
    image_branch_lr: float = 1e-5
    batch_size: int = 32
    epochs: int = 50
    early_stopping_patience: int = 10
    validation_split: float = 0.2

    # Loss
    focal_gamma: float = 2.0
    focal_alpha: float = 0.75

    # Augmentation
    enable_augmentation: bool = True
    rotation_degrees: float = 15.0

    # Output
    output_dir: str = "./models"
    class_names: list[str] = field(default_factory=lambda: ["false_alarm", "real_defect"])
