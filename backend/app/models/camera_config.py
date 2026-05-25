from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

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
    patchcore_model_path: Mapped[str] = mapped_column(
        String(512), nullable=False, comment="整体 PatchCore 模型路径",
    )
    yolo_model_path: Mapped[str] = mapped_column(
        String(512), nullable=False, comment="YOLO 检测模型路径",
    )
    detection_confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.25, comment="YOLO 置信度阈值",
    )
    patchcore_image_size: Mapped[int] = mapped_column(
        Integer, nullable=False, default=256, comment="PatchCore 输入图像尺寸",
    )
    patchcore_threshold: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.99, comment="PatchCore 异常阈值分位数",
    )
    region_mode_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="是否启用三分区模式",
    )
    region_upper_model_path: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="upper 区域 PatchCore 模型路径",
    )
    region_middle_model_path: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="middle 区域 PatchCore 模型路径",
    )
    region_lower_model_path: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="lower 区域 PatchCore 模型路径",
    )
