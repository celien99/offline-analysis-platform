from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ClusterListParams(BaseModel):
    status: str | None = None
    review_status: str | None = None
    defect_type: str | None = None
    seat_model_id: str | None = None
    camera_id: str | None = None
    min_samples: int | None = Field(default=None, ge=1)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class ClusterSummary(BaseModel):
    cluster_id: str
    seat_model_id: str | None = None
    camera_id: str | None = None
    name: str | None
    sample_count: int
    possible_type: str | None
    hdbscan_label: int
    hdbscan_probability: float | None
    umap_x: float | None
    umap_y: float | None
    status: str
    review_status: str | None
    defect_type: str | None
    representative_image_urls: list[str] = []
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    vlm_anomaly_type: str | None = None
    vlm_is_false_alarm: bool | None = None
    vlm_analyzed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ClusterDetailResponse(BaseModel):
    cluster_id: str
    name: str | None
    sample_count: int
    possible_type: str | None
    hdbscan_label: int
    hdbscan_probability: float | None
    umap_x: float | None
    umap_y: float | None
    status: str
    review_status: str | None
    defect_type: str | None
    seat_model_id: str | None = None
    camera_id: str | None = None
    representative_ids: list[str] = []
    representative_image_urls: list[str] = []
    centroid: list[float] | None = None
    reviewed_by: str | None
    reviewed_at: datetime | None
    vlm_anomaly_type: str | None = None
    vlm_is_false_alarm: bool | None = None
    vlm_reason: str | None = None
    vlm_confidence: float | None = None
    vlm_suggestion: str | None = None
    vlm_analyzed_at: datetime | None = None
    clustering_run_at: datetime
    created_at: datetime
    trace_id: str | None = None

    model_config = {"from_attributes": True}


class ClusterListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    clusters: list[ClusterSummary]


class ClusterTriggerRequest(BaseModel):
    """Request to trigger a new clustering run."""
    min_cluster_size: int | None = Field(default=None, ge=2)
    min_samples: int | None = Field(default=None, ge=1)
    anomaly_ids: list[str] | None = None
    seat_model_id: str | None = None
    camera_id: str | None = None
