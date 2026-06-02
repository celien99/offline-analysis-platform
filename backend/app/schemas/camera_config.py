# backend/app/schemas/camera_config.py
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


# ── Seat Model ──

class SeatModelCreate(BaseModel):
    seat_model_id: str = Field(..., max_length=128, description="座椅型号标识符")
    display_name: str = Field(..., max_length=256, description="显示名称")
    yolo_model_version_id: str | None = Field(default=None, description="全局 YOLO 检测模型版本 ID")
    projector_model_version_id: str | None = Field(default=None, description="全局 EmbeddingProjector 模型版本 ID")
    whitening_matrix_model_version_id: str | None = Field(default=None, description="全局 WhiteningTransform 模型版本 ID")


class SeatModelUpdate(BaseModel):
    seat_model_id: str | None = Field(default=None, max_length=128)
    display_name: str | None = Field(default=None, max_length=256)
    yolo_model_version_id: str | None = Field(default=None, description="全局 YOLO 检测模型版本 ID")
    projector_model_version_id: str | None = Field(default=None, description="全局 EmbeddingProjector 模型版本 ID")
    whitening_matrix_model_version_id: str | None = Field(default=None, description="全局 WhiteningTransform 模型版本 ID")


class SeatModelResponse(BaseModel):
    id: str
    seat_model_id: str
    display_name: str
    yolo_model_version_id: str | None = None
    projector_model_version_id: str | None = None
    whitening_matrix_model_version_id: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SeatModelWithCameras(SeatModelResponse):
    cameras: list[CameraConfigResponse] = []


# ── Camera Config ──

class CameraRegionBase(BaseModel):
    region_id: str = Field(..., max_length=64, description="ROI 区域 ID")
    box: list[float] = Field(..., min_length=4, max_length=4, description="归一化区域框 [x1, y1, x2, y2]")
    patchcore_model_version_id: str = Field(..., description="区域 PatchCore 模型版本 ID")
    enabled: bool = True
    sort_order: int = Field(default=0, ge=0)
    patchcore: dict[str, object] | None = Field(default=None, description="区域级 PatchCore 配置覆盖")

    @field_validator("box")
    @classmethod
    def validate_box(cls, value: list[float]) -> list[float]:
        if len(value) != 4:
            raise ValueError("box 必须包含 4 个坐标")
        x1, y1, x2, y2 = value
        if not (0.0 <= x1 < x2 <= 1.0 and 0.0 <= y1 < y2 <= 1.0):
            raise ValueError("box 必须满足 0 <= x1 < x2 <= 1 且 0 <= y1 < y2 <= 1")
        return value


class CameraRegionCreate(CameraRegionBase):
    pass


class CameraRegionResponse(CameraRegionBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CameraConfigCreate(BaseModel):
    camera_id: str = Field(..., max_length=128, description="相机标识符")
    efficientad_model_version_id: str = Field(..., description="PatchCore 模型版本 ID")
    detection_confidence: float = Field(default=0.25, ge=0.0, le=1.0)
    efficientad_image_size: int = Field(default=256, ge=64, le=1024)
    efficientad_threshold: float = Field(default=0.99, ge=0.0, le=1.0)
    filter_classifier_model_version_id: str | None = Field(default=None, description="Filter Classifier 模型版本 ID")
    normalizer_model_version_id: str | None = Field(default=None, description="CameraNormalizer stats 模型版本 ID")
    regions: list[CameraRegionCreate] = Field(default_factory=list, description="区域级 PatchCore 配置")


class CameraConfigUpdate(BaseModel):
    camera_id: str | None = Field(default=None, max_length=128)
    efficientad_model_version_id: str | None = Field(default=None)
    detection_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    efficientad_image_size: int | None = Field(default=None, ge=64, le=1024)
    efficientad_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    filter_classifier_model_version_id: str | None = Field(default=None)
    normalizer_model_version_id: str | None = Field(default=None, description="CameraNormalizer stats 模型版本 ID")
    regions: list[CameraRegionCreate] | None = Field(default=None, description="区域级 PatchCore 配置；传入时整体替换")


class CameraConfigResponse(BaseModel):
    id: str
    camera_id: str
    seat_model_id: str
    efficientad_model_version_id: str | None
    filter_classifier_model_version_id: str | None
    normalizer_model_version_id: str | None = None
    detection_confidence: float
    efficientad_image_size: int
    efficientad_threshold: float
    regions: list[CameraRegionResponse] = []
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
