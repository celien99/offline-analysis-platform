from __future__ import annotations

import json

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class SeatModel(BaseModel):
    __tablename__ = "seat_models"

    seat_model_id: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, index=True,
        comment="座椅型号标识符，如 seat_model_a",
    )
    display_name: Mapped[str] = mapped_column(
        String(256), nullable=False, comment="前端显示名称",
    )

    # 全局模型引用 → model_versions.id
    yolo_model_version_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("model_versions.id", ondelete="SET NULL"),
        nullable=True, comment="全局 YOLO 检测模型版本 ID",
    )
    projector_model_version_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("model_versions.id", ondelete="SET NULL"),
        nullable=True, comment="全局 EmbeddingProjector 模型版本 ID",
    )
    whitening_matrix_model_version_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("model_versions.id", ondelete="SET NULL"),
        nullable=True, comment="全局 WhiteningTransform 模型版本 ID",
    )


class CameraConfig(BaseModel):
    __tablename__ = "camera_configs"
    __table_args__ = (
        UniqueConstraint("seat_model_id", "camera_id", name="uq_seat_camera"),
    )

    camera_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="相机标识符",
    )
    seat_model_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("seat_models.seat_model_id", ondelete="CASCADE"),
        nullable=False, index=True, comment="所属座椅型号 seat_model_id",
    )

    # 模型引用 → model_versions.id
    efficientad_model_version_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("model_versions.id", ondelete="SET NULL"),
        nullable=True, comment="整体 EfficientAD 模型版本 ID",
    )

    detection_confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.25, comment="YOLO 置信度阈值",
    )
    efficientad_image_size: Mapped[int] = mapped_column(
        Integer, nullable=False, default=256, comment="EfficientAD 输入图像尺寸",
    )
    efficientad_threshold: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.99, comment="EfficientAD 异常阈值分位数",
    )

    # Filter Classifier 模型引用
    filter_classifier_model_version_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("model_versions.id", ondelete="SET NULL"),
        nullable=True, comment="Filter Classifier 模型版本 ID",
    )

    # CameraNormalizer stats 引用（每机位独立）
    normalizer_model_version_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("model_versions.id", ondelete="SET NULL"),
        nullable=True, comment="CameraNormalizer stats 模型版本 ID (per-camera mean/std .npz)",
    )

    regions: Mapped[list[CameraConfigRegion]] = relationship(
        "CameraConfigRegion",
        back_populates="camera_config",
        cascade="all, delete-orphan",
        order_by="CameraConfigRegion.sort_order",
    )


class CameraConfigRegion(BaseModel):
    __tablename__ = "camera_config_regions"
    __table_args__ = (
        UniqueConstraint("camera_config_id", "region_id", name="uq_camera_config_region"),
    )

    camera_config_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("camera_configs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属 camera_configs.id",
    )
    region_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="ROI 区域标识，如 upper/middle/lower",
    )
    x1: Mapped[float] = mapped_column(Float, nullable=False, comment="归一化区域左上角 x")
    y1: Mapped[float] = mapped_column(Float, nullable=False, comment="归一化区域左上角 y")
    x2: Mapped[float] = mapped_column(Float, nullable=False, comment="归一化区域右下角 x")
    y2: Mapped[float] = mapped_column(Float, nullable=False, comment="归一化区域右下角 y")
    patchcore_model_version_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("model_versions.id", ondelete="CASCADE"),
        nullable=False,
        comment="该区域使用的 PatchCore 模型版本 ID",
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="是否启用该区域",
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="前端展示和配置生成顺序",
    )
    patchcore_overrides_json: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="区域级 PatchCore 配置覆盖 JSON",
    )

    camera_config: Mapped[CameraConfig] = relationship(
        "CameraConfig",
        back_populates="regions",
    )

    @property
    def box(self) -> list[float]:
        return [self.x1, self.y1, self.x2, self.y2]

    @property
    def patchcore(self) -> dict[str, object] | None:
        if not self.patchcore_overrides_json:
            return None
        try:
            value = json.loads(self.patchcore_overrides_json)
        except json.JSONDecodeError:
            return None
        return value if isinstance(value, dict) else None
