from __future__ import annotations

from dataclasses import dataclass, field

from app.common.types import AnomalyId, CameraId, Timestamp


@dataclass
class AnomalySample:
    anomaly_id: AnomalyId
    camera_id: CameraId
    source: str
    anomaly_score: float | None
    date_folder: str
    original_path: str | None
    heatmap_path: str | None
    crop_path: str | None
    crop_paths: list[str] = field(default_factory=list)
    status: str = "pending"
    detected_at: Timestamp | None = None
    metadata: dict[str, object] = field(default_factory=dict)
    seat_model_id: str | None = None
    region_id: str | None = None


@dataclass
class AnomalySource:
    source_type: str
    count: int
    percentage: float
