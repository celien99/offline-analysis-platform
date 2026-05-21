from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AnomalyUploadRequest(BaseModel):
    camera_id: str = Field(..., max_length=64)
    source: str = Field(
        default="patchcore",
        pattern=r"^(patchcore|filter_classifier|rule_engine)$",
    )
    anomaly_score: float | None = Field(default=None, ge=0.0, le=1.0)
    date_folder: str = Field(..., max_length=16, description="YYYY-MM-DD")
    detected_at: datetime
    metadata: dict[str, object] | None = None


class AnomalyUploadResponse(BaseModel):
    anomaly_id: str
    status: str = "received"
    message: str = "Anomaly queued for processing"


class AnomalyQueryParams(BaseModel):
    camera_id: str | None = None
    source: str | None = None
    status: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    min_score: float | None = Field(default=None, ge=0.0, le=1.0)
    max_score: float | None = Field(default=None, ge=0.0, le=1.0)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class AnomalyResponse(BaseModel):
    anomaly_id: str
    camera_id: str
    source: str
    anomaly_score: float | None
    date_folder: str
    status: str
    detected_at: datetime
    original_url: str | None = None
    roi_url: str | None = None
    heatmap_url: str | None = None
    crop_url: str | None = None
    created_at: datetime
    trace_id: str | None = None

    model_config = {"from_attributes": True}
