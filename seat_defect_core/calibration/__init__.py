"""Feature calibration layer — cross-camera feature normalization, projection, and center tracking."""

from __future__ import annotations

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
    "EMACenterConfig",
    "ProjectionConfig",
    "WhiteningConfig",
]
