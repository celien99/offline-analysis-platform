"""EfficientAD 模型和推理配置。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EfficientADConfig:
    """EfficientAD 纹理异常检测配置。"""

    model_path: str = ""
    """训练后的 .pt 模型文件路径。"""

    device: str = "cpu"
    """推理设备：cpu / cuda / mps。"""

    input_size: int = 256
    """模型输入尺寸 (正方形)。"""

    teacher_backbone: str = "wide_resnet50_2"
    """教师网络 backbone。"""

    student_backbone: str = "resnet18"
    """学生网络 backbone。"""

    # 推理控制
    min_valid_pixel_ratio: float = 0.3
    """ROI 内有效像素最低比例，低于此值判定为 REJECT。"""

    # 阈值（训练时填充，推理时直接从模型文件读取）
    image_threshold: float = 0.0
    """图像级异常分数阈值。"""

    pixel_threshold: float = 0.0
    """像素级异常分数阈值。"""

    score_topk_ratio: float = 0.005
    """ROI 内用于图像级分数兜底的最高分像素比例。"""

    enable_pixel_threshold: bool = True
    """是否启用像素级强异常兜底判定。"""

    min_pixel_anomaly_area: int = 8
    """像素级强异常判定的最小面积（ROI 像素数）。"""

    min_pixel_anomaly_area_ratio: float = 0.0005
    """像素级强异常判定的最小面积比例。"""

    color_outlier_ratio_threshold: float = 0.05
    """颜色离群像素比例阈值，超过则判定为异常。"""

    use_ae: bool = True
    """推理时启用 ST+STAE 混合评分（AE map）。

    True:  ST + STAE 各 50% 混合，同时覆盖纹理和外观异常。
    False: ST-only，仅用 teacher-student distance（兼容旧训练模型）。
    仅对 eager 模式重建 wrapper 有效；TorchScript 模型使用 trace 时的设定。"""

    image_threshold_percentile: float = 99.0
    """训练后在正常验证图上计算图像级阈值的分位数。"""

    pixel_threshold_percentile: float = 99.9
    """训练后在正常验证图上计算像素级阈值的分位数。"""

    # 训练参数
    epochs: int = 100
    """训练轮数。"""

    batch_size: int = 16
    """训练批次大小。"""

    learning_rate: float = 0.0001
    """学习率。"""

    validation_split: float = 0.1
    """验证集比例。"""

    early_stopping_patience: int = 10
    """早停耐心轮数。"""
