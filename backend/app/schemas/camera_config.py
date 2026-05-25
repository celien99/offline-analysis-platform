# backend/app/schemas/camera_config.py
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ── Seat Model ──

class SeatModelCreate(BaseModel):
    seat_model_id: str = Field(..., max_length=128, description="座椅型号标识符")
    display_name: str = Field(..., max_length=256, description="显示名称")


class SeatModelUpdate(BaseModel):
    seat_model_id: str | None = Field(default=None, max_length=128)
    display_name: str | None = Field(default=None, max_length=256)


class SeatModelResponse(BaseModel):
    id: str
    seat_model_id: str
    display_name: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SeatModelWithCameras(SeatModelResponse):
    cameras: list[CameraConfigResponse] = []


# ── Camera Config ──

class CameraConfigCreate(BaseModel):
    camera_id: str = Field(..., max_length=128, description="相机标识符")
    patchcore_model_version_id: str = Field(..., description="PatchCore 模型版本 ID")
    yolo_model_version_id: str = Field(..., description="YOLO 检测模型版本 ID")
    detection_confidence: float = Field(default=0.25, ge=0.0, le=1.0)
    patchcore_image_size: int = Field(default=256, ge=64, le=1024)
    patchcore_threshold: float = Field(default=0.99, ge=0.0, le=1.0)
    region_mode_enabled: bool = False
    region_upper_model_version_id: str | None = Field(default=None, description="upper 区域模型版本 ID")
    region_middle_model_version_id: str | None = Field(default=None, description="middle 区域模型版本 ID")
    region_lower_model_version_id: str | None = Field(default=None, description="lower 区域模型版本 ID")


class CameraConfigUpdate(BaseModel):
    camera_id: str | None = Field(default=None, max_length=128)
    patchcore_model_version_id: str | None = Field(default=None)
    yolo_model_version_id: str | None = Field(default=None)
    detection_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    patchcore_image_size: int | None = Field(default=None, ge=64, le=1024)
    patchcore_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    region_mode_enabled: bool | None = None
    region_upper_model_version_id: str | None = Field(default=None)
    region_middle_model_version_id: str | None = Field(default=None)
    region_lower_model_version_id: str | None = Field(default=None)


class CameraConfigResponse(BaseModel):
    id: str
    camera_id: str
    seat_model_id: str
    patchcore_model_version_id: str | None
    yolo_model_version_id: str | None
    detection_confidence: float
    patchcore_image_size: int
    patchcore_threshold: float
    region_mode_enabled: bool
    region_upper_model_version_id: str | None
    region_middle_model_version_id: str | None
    region_lower_model_version_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Options (dropdown) ──

class CameraOption(BaseModel):
    camera_id: str


class SeatModelOption(BaseModel):
    seat_model_id: str
    display_name: str
    cameras: list[CameraOption] = []
