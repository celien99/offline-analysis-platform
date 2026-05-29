from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String, UniqueConstraint
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
