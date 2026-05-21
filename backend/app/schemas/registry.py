from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ModelDeployRequest(BaseModel):
    model_name: str = Field(...)
    version: str = Field(...)
    target: str = Field(..., description="production_line / camera_group")
    deployed_by: str | None = Field(default=None, max_length=64)


class ModelListParams(BaseModel):
    model_name: str | None = None
    model_type: str | None = None
    status: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class ModelVersionResponse(BaseModel):
    model_id: str
    model_name: str
    version: str
    model_type: str
    framework: str
    artifact_path: str
    metrics: dict[str, float] | None = None
    trained_at: datetime
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DeploymentResponse(BaseModel):
    deployment_id: str
    model_version_id: str
    model_name: str | None = None
    version: str | None = None
    target: str
    deployed_by: str | None
    deployed_at: datetime
    previous_version: str | None
    deployment_status: str

    model_config = {"from_attributes": True}


class ModelListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    models: list[ModelVersionResponse]
