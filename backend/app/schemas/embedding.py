from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class EmbeddingSearchRequest(BaseModel):
    anomaly_id: str = Field(..., description="Query by anomaly ID to find similar")
    top_k: int = Field(default=20, ge=1, le=100)
    threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class EmbeddingSearchByVectorRequest(BaseModel):
    vector: list[float] = Field(..., description="Query embedding vector")
    top_k: int = Field(default=20, ge=1, le=100)
    threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class EmbeddingResponse(BaseModel):
    embedding_id: str
    anomaly_id: str
    model_name: str
    model_version: str | None
    dimension: int
    similarity: float | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class EmbeddingSimilarResult(BaseModel):
    anomaly_id: str
    similarity: float
    camera_id: str | None = None
    date_folder: str | None = None
    crop_url: str | None = None
