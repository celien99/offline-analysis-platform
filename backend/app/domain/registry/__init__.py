from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ModelInfo:
    model_name: str
    version: str
    model_type: str
    framework: str
    artifact_path: str
    metrics: dict[str, float] | None = None
    trained_at: datetime | None = None
    status: str = "registered"


@dataclass
class DeploymentTarget:
    target: str
    model_version: str
    deployed_by: str | None = None
    previous_version: str | None = None
    status: str = "active"
