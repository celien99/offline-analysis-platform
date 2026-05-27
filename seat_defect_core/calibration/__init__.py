"""Feature calibration layer — cross-camera feature normalization, projection, and center tracking."""

from __future__ import annotations

from .camera_normalizer import (
    CameraNormalizer,
    CameraNormStats,
)
from .config import (
    CalibrationConfig,
    CameraNormConfig,
    EMACenterConfig,
    ProjectionConfig,
    WhiteningConfig,
)

__all__ = [
    "CalibrationConfig",
    "CameraNormConfig",
    "CameraNormalizer",
    "CameraNormStats",
    "EMACenterConfig",
    "ProjectionConfig",
    "WhiteningConfig",
]
