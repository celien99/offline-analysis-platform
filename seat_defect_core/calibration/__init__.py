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
from .feature_center import (
    DefectCenter,
    EMAFeatureCenter,
)
from .projector import (
    EmbeddingProjector,
    ProjectionParams,
)
from .whitening import (
    WhiteningTransform,
)

__all__ = [
    "CalibrationConfig",
    "CameraNormConfig",
    "CameraNormalizer",
    "CameraNormStats",
    "DefectCenter",
    "EmbeddingProjector",
    "EMAFeatureCenter",
    "EMACenterConfig",
    "ProjectionConfig",
    "ProjectionParams",
    "WhiteningConfig",
    "WhiteningTransform",
]
