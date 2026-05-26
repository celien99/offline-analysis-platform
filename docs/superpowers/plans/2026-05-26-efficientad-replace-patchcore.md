# EfficientAD 替代 PatchCore — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 seat_defect_core 中的 PatchCore 纹理异常检测完整替换为基于 anomalib 的 EfficientAD，同步调整前后端和配置。

**Architecture:** 新增 `efficientad/` 模块替代 `patchcore/` 模块，`EfficientADService` 提供 predict/predict_batch/load_bundle 接口，`TextureAnomalyResult` 精简为通用字段，前后端训练管理重命名适配。

**Tech Stack:** PyTorch, anomalib, FastAPI, Celery, React + Ant Design

---

### Task 1: 创建 EfficientAD 配置模型

**Files:**
- Create: `seat_defect_core/efficientad/__init__.py`
- Create: `seat_defect_core/efficientad/config.py`

- [ ] **Step 1: 创建 `efficientad/__init__.py` 模块入口**

```python
"""EfficientAD 纹理异常检测入口。"""

from .config import EfficientADConfig
from .engine import EfficientADService

__all__ = [
    "EfficientADConfig",
    "EfficientADService",
]
```

- [ ] **Step 2: 创建 `efficientad/config.py` 配置模型**

```python
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
```

- [ ] **Step 3: Commit**

```bash
git add seat_defect_core/efficientad/__init__.py seat_defect_core/efficientad/config.py
git commit -m "feat: add EfficientAD config model and module entry

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: 创建 EfficientAD 推理引擎

**Files:**
- Create: `seat_defect_core/efficientad/engine.py`

- [ ] **Step 1: 创建 `efficientad/engine.py`**

```python
"""EfficientAD 推理引擎。

基于 anomalib 的 EfficientAD 实现，加载 TorchScript 模型进行纹理异常检测。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

try:
    import torch
    import torch.nn.functional as F
except ImportError:
    torch = None
    F = None

from .config import EfficientADConfig
from ..core_types import TextureAnomalyResult

IMAGENET_MEAN = np.asarray([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.asarray([0.229, 0.224, 0.225], dtype=np.float32)


class EfficientADService:
    """加载训练后的 EfficientAD TorchScript 模型并执行推理。"""

    def __init__(self, config: EfficientADConfig) -> None:
        if torch is None:
            raise RuntimeError("EfficientAD 需要 PyTorch 运行环境")
        self.config = config
        self.device = _resolve_device(config.device)
        self.model: Optional[torch.jit.ScriptModule] = None
        self._image_threshold = config.image_threshold
        self._pixel_threshold = config.pixel_threshold
        if config.model_path:
            self._load_model(config.model_path)

    def _load_model(self, model_path: str) -> None:
        """加载 TorchScript 模型和阈值元数据。"""
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"EfficientAD 模型文件不存在: {model_path}")
        self.model = torch.jit.load(str(path), map_location=self.device)
        self.model.eval()
        # 从模型文件读取训练时保存的阈值
        meta_path = path.with_suffix(".meta.json")
        if meta_path.exists():
            import json
            meta = json.loads(meta_path.read_text("utf-8"))
            self._image_threshold = float(meta.get("image_threshold", self._image_threshold))
            self._pixel_threshold = float(meta.get("pixel_threshold", self._pixel_threshold))

    def predict(
        self,
        image: np.ndarray,
        target_mask: np.ndarray,
        ignore_mask: np.ndarray,
    ) -> TextureAnomalyResult:
        """对单张 ROI 图像执行异常检测。"""
        if self.model is None:
            raise RuntimeError("EfficientAD 模型未加载")

        original_h, original_w = image.shape[:2]
        valid_pixel_ratio = _compute_valid_pixel_ratio(target_mask, ignore_mask, image.shape[:2])

        # 计算有效像素比例，过低则 REJECT
        if valid_pixel_ratio < self.config.min_valid_pixel_ratio:
            return TextureAnomalyResult(
                score=0.0,
                threshold=self._image_threshold,
                is_anomaly=False,
                heatmap=np.zeros((original_h, original_w), dtype=np.float32),
                anomaly_map=np.zeros((original_h, original_w), dtype=np.float32),
                valid_pixel_ratio=valid_pixel_ratio,
            )

        # 预处理：BGR → RGB, resize, normalize
        input_tensor = _prepare_input(image, self.config.input_size).to(self.device)

        with torch.inference_mode():
            output = self.model(input_tensor)

        # 解析 anomalib 输出：通常是 (anomaly_map, anomaly_score)
        if isinstance(output, (tuple, list)):
            anomaly_map_tensor = output[0]
            anomaly_score = float(output[1].item()) if len(output) > 1 else 0.0
        elif torch.is_tensor(output):
            anomaly_map_tensor = output
            anomaly_score = float(anomaly_map_tensor.mean().item())
        else:
            raise RuntimeError(f"EfficientAD 输出格式不支持: {type(output)}")

        # anomaly_map 双线性插值回原始 ROI 尺寸
        anomaly_map = _resize_anomaly_map(anomaly_map_tensor, original_h, original_w)

        # 应用 ignore_mask 清零忽略区域
        if ignore_mask is not None and ignore_mask.any():
            ignore_binary = _to_binary_mask(ignore_mask, (original_h, original_w))
            anomaly_map[ignore_binary > 0] = 0.0

        # 热力图 = anomaly_map（直接用作可视化）
        heatmap = anomaly_map.copy()

        # 异常判定
        is_anomaly = anomaly_score > self._image_threshold

        return TextureAnomalyResult(
            score=anomaly_score,
            threshold=self._image_threshold,
            is_anomaly=is_anomaly,
            heatmap=heatmap,
            anomaly_map=anomaly_map,
            valid_pixel_ratio=valid_pixel_ratio,
        )

    def predict_batch(
        self,
        items: List[Tuple[np.ndarray, np.ndarray, np.ndarray]],
    ) -> List[TextureAnomalyResult]:
        """批量推理，逐张处理避免显存溢出。"""
        return [self.predict(image, target_mask, ignore_mask) for image, target_mask, ignore_mask in items]

    @classmethod
    def load_bundle(cls, model_path: str | Path) -> "EfficientADService":
        """从路径加载 EfficientAD 模型。"""
        config = EfficientADConfig(model_path=str(model_path))
        return cls(config)


def _resolve_device(requested: str) -> torch.device:
    """解析设备，支持自动回退。"""
    normalized = requested.strip().lower()
    if normalized.startswith("cuda") and torch.cuda.is_available():
        return torch.device(requested)
    if normalized == "mps" and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def _prepare_input(image: np.ndarray, input_size: int) -> torch.Tensor:
    """BGR → RGB → resize → normalize → tensor。"""
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB) if image.ndim == 3 and image.shape[2] == 3 else image
    resized = cv2.resize(rgb, (input_size, input_size), interpolation=cv2.INTER_AREA)
    normalized = (resized.astype(np.float32) / 255.0 - IMAGENET_MEAN) / IMAGENET_STD
    tensor = torch.from_numpy(np.transpose(normalized, (2, 0, 1))).unsqueeze(0).float()
    return tensor


def _resize_anomaly_map(
    anomaly_map_tensor: torch.Tensor,
    target_h: int,
    target_w: int,
) -> np.ndarray:
    """把模型输出的 anomaly_map 缩放到目标尺寸。"""
    amap = anomaly_map_tensor.detach().cpu()
    # anomalib 输出 shape: (1, 1, H, W) 或 (1, H, W)
    if amap.ndim == 4:
        amap = amap.squeeze(0).squeeze(0)
    elif amap.ndim == 3:
        amap = amap.squeeze(0)
    amap_np = amap.float().numpy()
    resized = cv2.resize(amap_np, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
    return resized.astype(np.float32)


def _compute_valid_pixel_ratio(
    target_mask: np.ndarray,
    ignore_mask: np.ndarray,
    shape: Tuple[int, int],
) -> float:
    """计算目标区域内有效像素比例。"""
    target_binary = _to_binary_mask(target_mask, shape)
    total = target_binary.sum()
    if total == 0:
        return 0.0
    ignore_binary = _to_binary_mask(ignore_mask, shape) if ignore_mask is not None and ignore_mask.any() else np.zeros(shape, dtype=np.uint8)
    valid = total - (ignore_binary * target_binary).sum()
    return float(valid / total)


def _to_binary_mask(mask: np.ndarray, shape: Tuple[int, int]) -> np.ndarray:
    """归一化为二值掩膜并缩放到目标尺寸。"""
    array = np.asarray(mask)
    if array.ndim == 3:
        if array.shape[2] == 4:
            array = array[:, :, 3]
        else:
            array = np.any(array > 0, axis=2)
    binary = (array > 0).astype(np.uint8)
    if binary.shape != shape:
        binary = cv2.resize(binary, (shape[1], shape[0]), interpolation=cv2.INTER_NEAREST)
    return binary
```

- [ ] **Step 2: Commit**

```bash
git add seat_defect_core/efficientad/engine.py
git commit -m "feat: add EfficientAD inference engine with TorchScript support

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: 创建 EfficientAD 训练入口

**Files:**
- Create: `seat_defect_core/training/efficientad.py`
- Modify: `seat_defect_core/training/__init__.py`

- [ ] **Step 1: 创建 `training/efficientad.py`**

```python
"""EfficientAD 模型训练。

基于 anomalib 的 EfficientAD 实现，从正常参考图像训练异常检测模型。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np
import torch


def train_efficientad(
    config: object,
    camera_id: str,
    good_image_paths: Sequence[str | Path],
    output_path: str,
) -> dict:
    """训练 EfficientAD 模型并导出 TorchScript。

    Args:
        config: InspectionConfig 或 JSON 配置文件路径。
        camera_id: 目标相机 ID。
        good_image_paths: 正常参考图像路径列表。
        output_path: 输出 .pt 文件路径。

    Returns:
        dict: {status, artifact_path, image_threshold, pixel_threshold}
    """
    from ..config import InspectionConfig
    from ..config_file import resolve_config
    from ..efficientad.config import EfficientADConfig

    # 解析配置
    if isinstance(config, (str, Path)):
        inspection_cfg = resolve_config(str(config))
    elif isinstance(config, InspectionConfig):
        inspection_cfg = config
    else:
        raise TypeError(f"config 类型不支持: {type(config)}")

    camera_config = _find_camera(inspection_cfg, camera_id)
    if camera_config is None:
        available = _list_camera_ids(inspection_cfg)
        raise ValueError(f"未找到相机 '{camera_id}'，可用相机: {available}")

    efficientad_cfg = camera_config.efficientad
    if efficientad_cfg is None:
        raise ValueError(f"相机 '{camera_id}' 未配置 efficientad 参数")

    # 加载正常图像
    images: list[np.ndarray] = []
    for img_path in good_image_paths:
        img_path = Path(img_path)
        if not img_path.exists():
            continue
        img = cv2.imread(str(img_path))
        if img is not None:
            images.append(img)

    if len(images) < 2:
        raise RuntimeError(f"正常参考图像不足 ({len(images)} 张)，至少需要 2 张")

    device = _resolve_train_device(efficientad_cfg.device)

    # 使用 anomalib 训练
    try:
        from anomalib.data import MVTec, MVTecDataset
        from anomalib.models import EfficientAd
        from anomalib.engine import Engine
    except ImportError:
        raise RuntimeError(
            "EfficientAD 训练依赖 anomalib 库，请安装: pip install anomalib"
        )

    # 创建临时数据集目录结构
    import tempfile
    import shutil

    tmp_dir = Path(tempfile.mkdtemp(prefix="efficientad_train_"))
    try:
        # anomalib MVTec 格式: {category}/train/good/, {category}/test/...
        category = camera_id.replace(" ", "_")
        good_dir = tmp_dir / category / "train" / "good"
        good_dir.mkdir(parents=True, exist_ok=True)

        for i, img in enumerate(images):
            cv2.imwrite(str(good_dir / f"{i:04d}.png"), img)

        # 配置 anomalib 模型
        model = EfficientAd(
            teacher_out_channels=384,
            model_size="medium",
        )

        # 训练
        engine = Engine(
            max_epochs=efficientad_cfg.epochs,
            devices=1 if device.type != "cpu" else 0,
            accelerator="gpu" if device.type == "cuda" else "cpu",
            default_root_dir=str(tmp_dir / "results"),
        )

        datamodule = MVTec(
            root=str(tmp_dir),
            category=category,
            image_size=(efficientad_cfg.input_size, efficientad_cfg.input_size),
            train_batch_size=efficientad_cfg.batch_size,
            eval_batch_size=efficientad_cfg.batch_size,
            num_workers=0,
        )

        engine.fit(model=model, datamodule=datamodule)

        # 导出 TorchScript
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        # 保存 TorchScript 模型
        model.eval()
        example_input = torch.randn(1, 3, efficientad_cfg.input_size, efficientad_cfg.input_size)
        traced = torch.jit.trace(model, example_input.to(device))
        traced.save(str(output))

        # 保存阈值元数据
        image_threshold = 0.5  # anomalib 默认
        pixel_threshold = 0.5
        meta = {
            "image_threshold": image_threshold,
            "pixel_threshold": pixel_threshold,
            "input_size": efficientad_cfg.input_size,
            "teacher_backbone": efficientad_cfg.teacher_backbone,
            "student_backbone": efficientad_cfg.student_backbone,
            "train_image_count": len(images),
            "epochs": efficientad_cfg.epochs,
        }
        meta_path = output.with_suffix(".meta.json")
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2))

        return {
            "status": "completed",
            "artifact_path": str(output),
            "image_threshold": image_threshold,
            "pixel_threshold": pixel_threshold,
            "train_image_count": len(images),
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def train_efficientad_cli() -> None:
    """CLI 入口：由 seat_defect_core.__main__ 调用。"""
    import argparse

    parser = argparse.ArgumentParser(description="训练 EfficientAD 模型")
    parser.add_argument("--config", required=True, help="检测配置文件路径 (JSON/INI)")
    parser.add_argument("--camera-id", required=True, help="目标相机 ID")
    parser.add_argument("--good-images", required=True, help="正常参考图像目录")
    parser.add_argument("--output", required=True, help="输出 .pt 文件路径")

    args = parser.parse_args()

    img_dir = Path(args.good_images)
    if not img_dir.is_dir():
        raise FileNotFoundError(f"图像目录不存在: {args.good_images}")

    image_paths: list[str] = []
    for ext in ("*.jpg", "*.jpeg", "*.png", "*.bmp"):
        image_paths.extend(str(p) for p in img_dir.glob(ext))
    if not image_paths:
        raise FileNotFoundError(f"目录中未找到图像文件: {args.good_images}")

    result = train_efficientad(
        config=args.config,
        camera_id=args.camera_id,
        good_image_paths=image_paths,
        output_path=args.output,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _find_camera(inspection_cfg, camera_id: str):
    """在配置中查找指定相机。"""
    from ..config import SeatModelConfig

    for cam in getattr(inspection_cfg, "cameras", []) or []:
        if cam.camera_id == camera_id:
            return cam
    seat_models: list = getattr(inspection_cfg, "seat_models", []) or []
    for sm in seat_models:
        for cam in getattr(sm, "cameras", []) or []:
            if cam.camera_id == camera_id:
                return cam
    return None


def _list_camera_ids(inspection_cfg) -> list[str]:
    """列出配置中所有相机 ID。"""
    ids: list[str] = []
    for cam in getattr(inspection_cfg, "cameras", []) or []:
        ids.append(cam.camera_id)
    for sm in getattr(inspection_cfg, "seat_models", []) or []:
        for cam in getattr(sm, "cameras", []) or []:
            ids.append(cam.camera_id)
    return ids


def _resolve_train_device(requested: str) -> torch.device:
    """解析训练设备。"""
    normalized = requested.strip().lower()
    if normalized.startswith("cuda") and torch.cuda.is_available():
        return torch.device("cuda")
    if normalized == "mps" and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")
```

- [ ] **Step 2: 更新 `training/__init__.py`**

Read current file first, then replace content:

```python
"""EfficientAD 模型训练。"""

from .efficientad import train_efficientad, train_efficientad_cli

__all__ = [
    "train_efficientad",
    "train_efficientad_cli",
]
```

- [ ] **Step 3: Commit**

```bash
git add seat_defect_core/training/efficientad.py seat_defect_core/training/__init__.py
git commit -m "feat: add EfficientAD training entry using anomalib

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 4: 精简 TextureAnomalyResult 并更新 core_types

**Files:**
- Modify: `seat_defect_core/core_types/results.py`
- Modify: `seat_defect_core/core_types/__init__.py`

- [ ] **Step 1: 替换 `TextureAnomalyResult` 为精简版本**

移除 PatchCore 特有字段，保留通用字段：

```python
"""主检测流程输出结果类型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .geometry import BoundingBox
from .pipeline import DetectionResult, ImageQualityDecision


@dataclass
class TextureAnomalyResult:
    """纹理异常检测分支输出。"""

    score: float
    """图像级异常分数 (0-1)。"""

    threshold: float
    """异常判定阈值。"""

    is_anomaly: bool
    """是否判定为异常。"""

    heatmap: Any
    """ROI 坐标系下的异常热力图。"""

    anomaly_map: Any
    """模型原始输出异常图。"""

    valid_pixel_ratio: float = 1.0
    """ROI 内有效像素比例。"""


@dataclass
class InspectionError:
    """结构化错误，供外部系统稳定识别。"""

    code: str
    """稳定错误码。"""

    message: str
    """面向日志/调试的错误信息。"""

    stage: str
    """错误发生阶段。"""


@dataclass
class FilterClassifierResult:
    """过滤器分类器分支输出。"""

    is_real_defect: bool
    """分类器是否判定为真实缺陷（True=保留NG, False=误报应抑制）。"""

    confidence: float
    """预测类别的 softmax 置信度。"""

    real_defect_score: float
    """real_defect 类的 softmax 输出。"""

    false_alarm_score: float
    """false_alarm 类的 softmax 输出。"""

    class_id: int
    """预测类别ID：1=real_defect, 0=false_alarm。"""

    diagnostics: Dict[str, float] = field(default_factory=dict)
    """推理诊断指标（延迟、预处理时间等）。"""


@dataclass
class RegionAnomalyResult:
    """单个局部区域的异常检测输出。"""

    region_id: str
    """区域 ID。"""

    status: str
    """区域状态：OK / NG / REJECT。"""

    reason: str
    """区域状态原因。"""

    box: BoundingBox
    """标准 ROI 坐标系下的区域矩形框。"""

    texture_result: Optional[TextureAnomalyResult] = None
    """该区域的纹理异常结果。"""

    efficientad_model_path: Optional[str] = None
    """该区域使用的 EfficientAD 模型路径。"""

    artifact_paths: Dict[str, str] = field(default_factory=dict)
    """该区域关联的调试产物路径。"""

    timings_ms: Dict[str, float] = field(default_factory=dict)
    """该区域各阶段耗时，单位毫秒。"""

    error: Optional[InspectionError] = None
    """该区域结构化错误。"""

    sample: Optional[Any] = field(default=None, repr=False, compare=False)
    """运行时复用的区域 ROI 样本，不参与公开序列化。"""


@dataclass
class CameraInspectionResult:
    """单机位最终检测结果。"""

    camera_id: str
    """机位 ID。"""

    frame_id: str
    """帧编号。"""

    source: str
    """输入来源标识。"""

    source_kind: str
    """输入来源类型。"""

    status: str
    """单机位状态：OK / NG / REJECT。"""

    reason: str
    """单机位状态原因。"""

    seat_model_id: Optional[str] = None
    """本次检测使用的座椅型号 ID。"""

    quality: Optional[ImageQualityDecision] = None
    """图像质量判定结果。"""

    detection: Optional[DetectionResult] = None
    """YOLO 检测结果。"""

    texture_result: Optional[TextureAnomalyResult] = None
    """完整 ROI 模式下的纹理异常结果。"""

    region_results: List[RegionAnomalyResult] = field(default_factory=list)
    """regions 模式下的区域检测结果。"""

    filter_result: Optional[FilterClassifierResult] = None
    """过滤器分类器分支结果。"""

    crop_box: Optional[BoundingBox] = None
    """原图坐标系下最终使用的 ROI 裁剪框。"""

    artifact_paths: Dict[str, str] = field(default_factory=dict)
    """该机位关联的调试产物路径。"""

    timings_ms: Dict[str, float] = field(default_factory=dict)
    """该机位各阶段耗时，单位毫秒。"""

    error: Optional[InspectionError] = None
    """该机位结构化错误。"""

    overlay_image: Optional[Any] = field(default=None, repr=False, compare=False)
    """叠加了异常热力图的 BGR 调试图片，供调用方直接消费。"""

    original_image: Optional[Any] = field(default=None, repr=False, compare=False)
    """本次检测输入的原始 BGR 图像，供 NG 上传链路使用。"""

    roi_image: Optional[Any] = field(default=None, repr=False, compare=False)
    """原始 ROI 裁剪图像（未缩放到标准画布），供离线平台展示使用。"""

    roi_aligned_image: Optional[Any] = field(default=None, repr=False, compare=False)
    """标准 ROI 对齐图像 (BGR)，不含热力图叠加，供上传离线平台使用。"""


@dataclass
class InspectionResult:
    """多机位融合后的整件检测结果。"""

    part_id: str
    """工件编号。"""

    frame_id: str
    """本次检测批次帧编号。"""

    timestamp: str
    """本次检测时间戳。"""

    status: str
    """整件状态：OK / NG / REJECT。"""

    decision_reason: str
    """整件融合判定原因。"""

    seat_model_id: Optional[str] = None
    """本次检测使用的座椅型号 ID。"""

    camera_results: List[CameraInspectionResult] = field(default_factory=list)
    """所有机位检测结果。"""

    timings_ms: Dict[str, float] = field(default_factory=dict)
    """整件检测各阶段耗时，单位毫秒。"""


@dataclass
class InspectionResponse:
    """core 对外返回的检测响应。"""

    result: InspectionResult
    """完整检测结果对象。"""

    report_path: str
    """最新检测报告 JSON 路径。"""

    artifact_paths: Dict[str, Dict[str, str]]
    """按机位聚合的调试产物路径。"""

    @property
    def status(self) -> str:
        """整件状态快捷访问。"""
        return self.result.status

    @property
    def decision_reason(self) -> str:
        """整件判定原因快捷访问。"""
        return self.result.decision_reason

    @property
    def part_id(self) -> str:
        """工件编号快捷访问。"""
        return self.result.part_id

    @property
    def seat_model_id(self) -> Optional[str]:
        """座椅型号 ID 快捷访问。"""
        return self.result.seat_model_id

    def to_dict(self) -> Dict[str, Any]:
        """转换为适合外部系统序列化的字典。"""
        from ..serialization import inspection_result_to_dict

        payload = inspection_result_to_dict(self.result)
        payload.update(
            {
                "report_path": self.report_path,
                "artifact_paths": self.artifact_paths,
            }
        )
        return payload


__all__ = [
    "CameraInspectionResult",
    "FilterClassifierResult",
    "InspectionError",
    "InspectionResponse",
    "InspectionResult",
    "RegionAnomalyResult",
    "TextureAnomalyResult",
]
```

- [ ] **Step 2: 更新 `core_types/__init__.py`**

Read current file first, then update exports:

```python
"""core 对外类型。"""

from .geometry import BoundingBox
from .input import InspectionFrame
from .pipeline import DetectionResult, ImageQualityDecision, FilterClassifierConfig, RoiRefineResult
from .results import (
    CameraInspectionResult,
    FilterClassifierResult,
    InspectionError,
    InspectionResponse,
    InspectionResult,
    RegionAnomalyResult,
    TextureAnomalyResult,
)

__all__ = [
    "BoundingBox",
    "CameraInspectionResult",
    "DetectionResult",
    "FilterClassifierConfig",
    "FilterClassifierResult",
    "ImageQualityDecision",
    "InspectionError",
    "InspectionFrame",
    "InspectionResponse",
    "InspectionResult",
    "RegionAnomalyResult",
    "RoiRefineResult",
    "TextureAnomalyResult",
]
```

- [ ] **Step 3: Commit**

```bash
git add seat_defect_core/core_types/results.py seat_defect_core/core_types/__init__.py
git commit -m "refactor: simplify TextureAnomalyResult, rename RegionAnomalyResult

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 5: 更新 config.py — 替换 PatchCoreConfig 为 EfficientADConfig

**Files:**
- Modify: `seat_defect_core/config.py`

- [ ] **Step 1: 替换 `PatchCoreConfig` 和 `ColorBranchConfig` 为 `EfficientADConfig`**

Read current file, then apply these edits:

1. Remove `PatchCoreConfig` dataclass (lines 60-104)
2. Remove `ColorBranchConfig` dataclass (lines 107-115)
3. Import `EfficientADConfig` from `efficientad`
4. In `RegionConfig`: `patchcore_model_path` → `efficientad_model_path`, `patchcore: Optional[PatchCoreConfig]` → `efficientad: Optional[EfficientADConfig]`
5. In `CameraConfig`: `patchcore_model_path` → `efficientad_model_path`, `patchcore: PatchCoreConfig` → `efficientad: EfficientADConfig`, remove `color_branch: ColorBranchConfig`, remove `color_insensitive_mode`

- [ ] **Step 2: 验证 Python 语法**

```bash
cd seat_defect_core && ../.venv/bin/python -c "from seat_defect_core.config import CameraConfig, EfficientADConfig; print('OK')"
```

- [ ] **Step 3: Commit**

---

### Task 6: 更新 service/core.py — InspectionService 适配 EfficientAD

**Files:**
- Modify: `seat_defect_core/service/core.py`

关键修改：
- 移除 `from ..patchcore import LoadedModelBundle, PatchCoreService` 和 `color_branch` 导入
- 新增 `from ..efficientad import EfficientADService`
- `LoadedModelBundle` → 简化为直接使用 `EfficientADService`
- `PatchCorePredictorPool` → `EfficientADPredictor`
- `ModelBundleCache` → `AnomalyModelCache`
- `CameraPipeline` 移除质量检查和 ROI 之外无需改动
- `warmup()` 适配新模型加载

- [ ] **Step 1: 重写 `service/core.py`**

完整重写内容见 commit。

- [ ] **Step 2: Commit**

---

### Task 7: 更新 service/inspection_camera.py — 检测流程适配

**Files:**
- Modify: `seat_defect_core/service/inspection_camera.py`

关键修改：
- `RegionPatchCorePlan` → `RegionAnomalyPlan`，`patchcore_items` → `anomaly_items`
- 移除 `_predict_color_branch`
- `finish_region_patchcore_plan` → `finish_region_anomaly_plan`
- `_merge_region_status` 简化（去掉 color_result 参数）
- `inspect_prepared_camera` 中的 color_result 和 filter_result 逻辑简化

- [ ] **Step 1: 重写 `service/inspection_camera.py`**

完整重写内容见 commit。

- [ ] **Step 2: Commit**

---

### Task 8: 移除 patchcore/ 目录，更新 __main__.py 和 serialization.py

**Files:**
- Delete: `seat_defect_core/patchcore/` (entire directory)
- Delete: `seat_defect_core/training/patchcore.py`
- Modify: `seat_defect_core/__main__.py`
- Modify: `seat_defect_core/serialization.py`
- Modify: `seat_defect_core/__init__.py`

- [ ] **Step 1: 删除 patchcore 目录和旧训练文件**

```bash
rm -rf seat_defect_core/patchcore/
rm seat_defect_core/training/patchcore.py
```

- [ ] **Step 2: 更新 `__main__.py`**

将 `train-patchcore` 子命令替换为 `train-efficientad`：

```python
subparsers.add_parser("train-efficientad", help="训练 EfficientAD 模型")
```

对应的处理分支：
```python
elif args.command == "train-efficientad":
    from .training.efficientad import train_efficientad_cli
    train_efficientad_cli()
```

- [ ] **Step 3: 更新 `serialization.py`**

移除 `ColorAnomalyResult` 序列化；`TextureAnomalyResult` 序列化适配新字段；`RegionPatchCoreResult` → `RegionAnomalyResult`。

- [ ] **Step 4: 更新 `__init__.py`**

移除 patchcore 相关 import 和 __all__ 导出。

- [ ] **Step 5: Commit**

```bash
git add -A seat_defect_core/
git commit -m "refactor: remove patchcore module, replace with efficientad in service layer

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 9: 更新 seat_defect_core 配置文件

**Files:**
- Modify: `seat_defect_core/config.example.json`
- Modify: `seat_defect_core/config.training.example.json`
- Modify: `seat_defect_core/config.closed_loop_test.json`
- Modify: `seat_defect_core/pyproject.toml`

- [ ] **Step 1: 更新三个 JSON 配置文件**

将 `patchcore` 替换为 `efficientad`，`patchcore_model_path` 替换为 `efficientad_model_path`，移除 `color_branch` 块。

- [ ] **Step 2: 更新 `pyproject.toml`**

移除 FAISS 依赖，新增 `anomalib>=1.0.0`。

- [ ] **Step 3: Commit**

```bash
git add seat_defect_core/config*.json seat_defect_core/pyproject.toml
git commit -m "refactor: update config files for EfficientAD migration

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 10: 后端迁移 — 重命名和适配

**Files:**
- Rename: `backend/app/schemas/patchcore_training.py` → `backend/app/schemas/efficientad_training.py`
- Rename: `backend/app/api/patchcore_training/` → `backend/app/api/efficientad_training/`
- Rename: `backend/app/workers/patchcore_training_worker/` → `backend/app/workers/efficientad_training_worker/`
- Modify: 各重命名文件内部 import 和引用

- [ ] **Step 1: 执行重命名**

```bash
# schemas
mv backend/app/schemas/patchcore_training.py backend/app/schemas/efficientad_training.py

# API router
mv backend/app/api/patchcore_training backend/app/api/efficientad_training

# Worker
mv backend/app/workers/patchcore_training_worker backend/app/workers/efficientad_training_worker
```

- [ ] **Step 2: 更新文件内容**

- `efficientad_training.py`: `PatchCoreTrainingStartRequest` → `EfficientADTrainingStartRequest`
- `efficientad_training/router.py`: 路由前缀 `/api/efficientad-training`，引用新的 task 和 schema
- `efficientad_training_worker/tasks.py`: `train_patchcore_model` → `train_efficientad_model`，subprocess 调用 `train-efficientad`，模型格式 `.pt`，`model_type="efficientad"`

- [ ] **Step 3: Commit**

---

### Task 11: 前端迁移 — 重命名和适配

**Files:**
- Rename: `frontend/src/types/patchcore-training.ts` → `frontend/src/types/efficientad-training.ts`
- Rename: `frontend/src/api/patchcore-training.ts` → `frontend/src/api/efficientad-training.ts`
- Modify: `frontend/src/features/training/index.tsx`
- Modify: `frontend/src/hooks/queries.ts`

- [ ] **Step 1: 重命名文件**

```bash
mv frontend/src/types/patchcore-training.ts frontend/src/types/efficientad-training.ts
mv frontend/src/api/patchcore-training.ts frontend/src/api/efficientad-training.ts
```

- [ ] **Step 2: 更新 `efficientad-training.ts` API**

```typescript
import http from "./client";

export const efficientadTrainingApi = {
  start: (formData: FormData) =>
    http.post<{ status: string; message: string; task_id: string }>(
      "/efficientad-training/start",
      formData,
      { headers: { "Content-Type": "multipart/form-data" } },
    ).then((res) => res.data),
};
```

- [ ] **Step 3: 更新 `training/index.tsx`**

- Tab 标签 "PatchCore 训练" → "EfficientAD 训练"
- `usePatchCoreTrainingStart` → `useEfficientADTrainingStart`
- `patchcoreStart` → `efficientadStart`
- `modelTypeColor("patchcore")` → `modelTypeColor("efficientad")` 颜色 `purple` → `cyan`

- [ ] **Step 4: 更新 `hooks/queries.ts`**

Hook 名称和 API 引用适配。

- [ ] **Step 5: Commit**

---

### Task 12: 更新 README 和残留引用

**Files:**
- Modify: `README.md`
- Modify: `seat_defect_core/USAGE.md`

- [ ] **Step 1: 更新 README 中的命令**

将 `train-patchcore` 替换为 `train-efficientad`，更新训练流程说明。

- [ ] **Step 2: 更新 USAGE.md**

将所有 PatchCore 引用替换为 EfficientAD。

- [ ] **Step 3: 全局搜索残留的 PatchCore 引用**

```bash
rg -l "patchcore" --type-not json --type-not lock . | grep -v ".git/" | grep -v "node_modules/" | grep -v ".venv/"
```

逐文件检查和修复。

- [ ] **Step 4: Commit**

---

### Task 13: 验证 — 语法检查和类型检查

- [ ] **Step 1: seat_defect_core 语法检查**

```bash
cd seat_defect_core && .venv/bin/python -c "
from seat_defect_core.efficientad import EfficientADService, EfficientADConfig
from seat_defect_core.core_types import TextureAnomalyResult, RegionAnomalyResult
from seat_defect_core.config import CameraConfig, InspectionConfig
print('All imports OK')
"
```

- [ ] **Step 2: backend 语法检查**

```bash
cd backend && uv run python -c "
from app.schemas.efficientad_training import EfficientADTrainingStartRequest
from app.workers.efficientad_training_worker.tasks import train_efficientad_model
print('Backend imports OK')
"
```

- [ ] **Step 3: frontend typecheck**

```bash
cd frontend && pnpm run build
```

- [ ] **Step 4: Commit any fixes**
