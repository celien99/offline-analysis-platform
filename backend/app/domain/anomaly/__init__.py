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
    roi_path: str | None
    heatmap_path: str | None
    crop_path: str | None
    status: str = "pending"
    detected_at: Timestamp | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class AnomalySource:
    source_type: str
    count: int
    percentage: float
