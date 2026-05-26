from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas import CURRENT_SCHEMA_VERSION


class AnomalyUploadResponse(BaseModel):
    anomaly_ids: list[str]
    count: int
    status: str = "received"
    message: str = "Anomaly queued for processing"
    schema_version: str = CURRENT_SCHEMA_VERSION


class AnomalyQueryParams(BaseModel):
    camera_id: str | None = None
    seat_model_id: str | None = None
    region_id: str | None = None
    source: str | None = None
    status: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    min_score: float | None = Field(default=None, ge=0.0)
    max_score: float | None = Field(default=None, ge=0.0)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class AnomalyResponse(BaseModel):
    anomaly_id: str
    camera_id: str
    seat_model_id: str | None = None
    region_id: str | None = None
    source: str
    anomaly_score: float | None
    date_folder: str
    status: str
    detected_at: datetime
    original_url: str | None = None
    heatmap_url: str | None = None
    crop_url: str | None = None
    crop_urls: list[str] = []
    proposal_count: int = 0
    proposals_json: Optional[str] = None
    cluster_id: str | None = None
    created_at: datetime
    trace_id: str | None = None

    model_config = {"from_attributes": True}
