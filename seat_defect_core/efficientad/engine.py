"""EfficientAD 推理引擎。

基于 anomalib 的 EfficientAD 实现，加载 TorchScript 模型进行纹理异常检测。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import cv2
import numpy as np

try:
    import torch
except ImportError:
    torch = None

from .config import EfficientADConfig
from ..core_types import TextureAnomalyResult

_logger = logging.getLogger(__name__)

IMAGENET_MEAN = np.asarray([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.asarray([0.229, 0.224, 0.225], dtype=np.float32)

# ImageNet 均值灰（RGB uint8），用于填充非目标区域避免黑边引入异常响应
IMAGENET_MEAN_GRAY_RGB = np.asarray([124, 116, 104], dtype=np.uint8)


class EfficientADService:
    """加载训练后的 EfficientAD TorchScript 模型并执行推理。"""

    def __init__(self, config: EfficientADConfig) -> None:
        if torch is None:
            raise RuntimeError("EfficientAD 需要 PyTorch 运行环境")
        self.config = config
        self.device = _resolve_device(config.device)
        self.model: Optional[torch.jit.ScriptModule] = None
        self._feature_model: Optional[torch.nn.Module] = None
        self._image_threshold = config.image_threshold
        self._threshold_from_meta = False
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
            loaded_threshold = float(meta.get("image_threshold", self._image_threshold))
            if loaded_threshold > 0.0:
                self._image_threshold = loaded_threshold
                self._threshold_from_meta = True
        if not self._threshold_from_meta:
            _logger.warning(
                "efficientad_threshold_not_loaded",
                extra={
                    "model_path": model_path,
                    "fallback_threshold": self._image_threshold,
                    "hint": "请检查 .meta.json 是否与模型文件在同一目录，或重新训练生成阈值",
                },
            )

        # 尝试加载特征提取模型（state_dict）
        state_dict_path = path.with_suffix(".state_dict.pt")
        if state_dict_path.exists():
            self._load_feature_model(str(state_dict_path))

    def _load_feature_model(self, state_dict_path: str) -> None:
        """尝试从 state_dict 重建模型用于多尺度特征提取。"""
        try:
            from anomalib.models import EfficientAd as EfficientAdModel

            state_dict = torch.load(state_dict_path, map_location=self.device)
            feature_model = EfficientAdModel(
                teacher_out_channels=384,
                model_size="medium",
            )
            feature_model.load_state_dict(state_dict)
            feature_model.to(self.device)
            feature_model.eval()
            self._feature_model = feature_model
            _logger.info("efficientad_feature_model_loaded")
        except Exception:
            _logger.debug("efficientad_feature_model_unavailable", exc_info=True)

    @property
    def image_threshold(self) -> float:
        return self._image_threshold

    @property
    def has_features(self) -> bool:
        """是否支持多尺度特征提取。"""
        return self._feature_model is not None

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

        # 预处理：BGR → RGB, resize, normalize，非目标区域用 ImageNet 均值灰填充
        input_tensor = _prepare_input(image, self.config.input_size).to(self.device)

        with torch.inference_mode():
            output = self.model(input_tensor)

        # 解析 anomalib 输出：通常是 (anomaly_map, anomaly_score)
        if isinstance(output, (tuple, list)):
            anomaly_map_tensor = output[0]
            anomaly_score_raw = float(output[1].item()) if len(output) > 1 else 0.0
        elif torch.is_tensor(output):
            anomaly_map_tensor = output
            anomaly_score_raw = float(anomaly_map_tensor.mean().item())
        else:
            raise RuntimeError(f"EfficientAD 输出格式不支持: {type(output)}")

        # anomaly_map 双线性插值回原始 ROI 尺寸
        anomaly_map = _resize_anomaly_map(anomaly_map_tensor, original_h, original_w)

        # 应用 ignore_mask 清零忽略区域（边缘像素）
        if ignore_mask is not None and ignore_mask.any():
            ignore_binary = _to_binary_mask(ignore_mask, (original_h, original_w))
            anomaly_map[ignore_binary > 0] = 0.0

        # 构建目标区域二值掩膜，清零非目标区域（letterbox padding 等）
        target_binary = _to_binary_mask(target_mask, (original_h, original_w))

        # 仅从目标区域计算 image-level anomaly_score，避免 padding 区域噪声污染
        target_pixels = anomaly_map[target_binary > 0]
        if target_pixels.size > 0:
            anomaly_score = float(target_pixels.mean())
        else:
            anomaly_score = anomaly_score_raw

        # 热力图：以阈值为锚点做归一化，阈值≈0.5，2×阈值≈1.0
        # 正常区域（远低于阈值）→ dark blue，边界 → yellow，异常 → red
        heatmap = _normalize_heatmap(anomaly_map, target_binary, self._image_threshold)

        # 统计强异常 patch（用于规则引擎后处理）
        strong_patch_count, strong_patch_ratio = _compute_strong_patches(
            anomaly_map, target_binary, self._image_threshold
        )

        # 异常判定
        is_anomaly = anomaly_score > self._image_threshold

        # 多尺度特征提取（如果可用）
        features = self._extract_features(input_tensor) if self._feature_model is not None else None

        return TextureAnomalyResult(
            score=anomaly_score,
            threshold=self._image_threshold,
            is_anomaly=is_anomaly,
            heatmap=heatmap,
            anomaly_map=anomaly_map,
            valid_pixel_ratio=valid_pixel_ratio,
            features=features,
            strong_patch_count=strong_patch_count,
            strong_patch_ratio=strong_patch_ratio,
        )

    def predict_batch(
        self,
        items: List[Tuple[np.ndarray, np.ndarray, np.ndarray]],
    ) -> List[TextureAnomalyResult]:
        """批量推理，逐张处理避免显存溢出。"""
        return [self.predict(image, target_mask, ignore_mask) for image, target_mask, ignore_mask in items]

    def _extract_features(self, input_tensor: torch.Tensor) -> dict[str, np.ndarray]:
        """从 EfficientAD 模型提取多尺度 teacher/student 特征图。

        通过 forward hook 捕获中间层输出，返回 calibration 模块所需的特征字典。
        如果模型结构不匹配则返回空 dict。
        """
        if self._feature_model is None:
            return {}

        features: dict[str, torch.Tensor] = {}
        handles: list[torch.utils.hooks.RemovableHandle] = []

        def _make_hook(name: str) -> Callable[[torch.nn.Module, torch.Tensor, torch.Tensor], None]:
            def hook(_module: torch.nn.Module, _input: torch.Tensor, output: torch.Tensor) -> None:
                features[name] = output.detach()

            return hook

        # 注册 teacher 各层 hook
        for module_name, module in self._feature_model.named_modules():
            # teacher 特征层：layer1 / layer2 / layer3
            if module_name.endswith("teacher.layer1"):
                handles.append(module.register_forward_hook(_make_hook("teacher_l1")))
            elif module_name.endswith("teacher.layer2"):
                handles.append(module.register_forward_hook(_make_hook("teacher_l2")))
            elif module_name.endswith("teacher.layer3"):
                handles.append(module.register_forward_hook(_make_hook("teacher_l3")))
            # student 特征层
            elif module_name.endswith("student.layer1"):
                handles.append(module.register_forward_hook(_make_hook("student_l1")))

        try:
            with torch.inference_mode():
                self._feature_model(input_tensor)
        except Exception:
            _logger.debug("efficientad_feature_extraction_failed", exc_info=True)
            return {}
        finally:
            for h in handles:
                h.remove()

        if not features:
            return {}

        result: dict[str, np.ndarray] = {}
        for key, tensor in features.items():
            result[key] = tensor.squeeze(0).permute(1, 2, 0).cpu().float().numpy()

        # 计算 teacher-student 差异特征
        if "teacher_l1" in result and "student_l1" in result:
            t_l1 = result["teacher_l1"]
            s_l1 = result["student_l1"]
            # 对齐 spatial 尺寸（student 可能分辨率不同）
            if t_l1.shape[:2] != s_l1.shape[:2]:
                s_l1 = cv2.resize(s_l1, (t_l1.shape[1], t_l1.shape[0]), interpolation=cv2.INTER_LINEAR)
            result["difference"] = (t_l1 - s_l1).astype(np.float32)

        return result

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
    """BGR 或 BGRA → RGB → resize → 非目标区域用 ImageNet 均值灰填充 → normalize → tensor。

    当输入包含 alpha 通道时，alpha=0 的区域（letterbox padding）会被填充为
    ImageNet 均值灰，避免黑边在 EfficientAD 中产生异常响应。
    """
    has_alpha = image.ndim == 3 and image.shape[2] == 4
    if has_alpha:
        alpha = image[:, :, 3].copy()
        image = image[:, :, :3]

    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    # 保持宽高比的 resize（letterbox 等效：先 resize 再放 canvas 中央）
    h, w = rgb.shape[:2]
    scale = min(float(input_size) / float(h), float(input_size) / float(w))
    new_h = max(1, int(round(h * scale)))
    new_w = max(1, int(round(w * scale)))
    resized = cv2.resize(rgb, (new_w, new_h), interpolation=cv2.INTER_AREA)

    # 放在 ImageNet 均值灰画布中央
    canvas = np.full(
        (input_size, input_size, 3),
        IMAGENET_MEAN_GRAY_RGB,
        dtype=np.uint8,
    )
    offset_y = (input_size - new_h) // 2
    offset_x = (input_size - new_w) // 2
    canvas[offset_y : offset_y + new_h, offset_x : offset_x + new_w] = resized

    # 如果原图有 alpha 通道，将 alpha=0 的 padding 也填充为均值灰
    if has_alpha:
        alpha_resized = cv2.resize(alpha, (new_w, new_h), interpolation=cv2.INTER_NEAREST)
        alpha_canvas = np.zeros((input_size, input_size), dtype=np.uint8)
        alpha_canvas[offset_y : offset_y + new_h, offset_x : offset_x + new_w] = alpha_resized
        non_target_mask = alpha_canvas == 0
        canvas[non_target_mask] = IMAGENET_MEAN_GRAY_RGB

    normalized = (canvas.astype(np.float32) / 255.0 - IMAGENET_MEAN) / IMAGENET_STD
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
    ignore_binary = (
        _to_binary_mask(ignore_mask, shape)
        if ignore_mask is not None and ignore_mask.any()
        else np.zeros(shape, dtype=np.uint8)
    )
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


def _compute_strong_patches(
    anomaly_map: np.ndarray,
    target_binary: np.ndarray,
    threshold: float,
) -> Tuple[int, float]:
    """统计目标区域内超过阈值的强异常连通域数量和面积比例。"""
    target_pixels = target_binary.sum()
    if target_pixels == 0:
        return 0, 0.0

    strong_binary: np.ndarray = (anomaly_map > threshold).astype(np.uint8)
    strong_mask: np.ndarray = strong_binary * target_binary
    strong_area: int = int(strong_mask.sum())
    if strong_area == 0:
        return 0, 0.0

    # 连通域分析
    num_labels, labels, _stats, _centroids = cv2.connectedComponentsWithStats(
        strong_mask, connectivity=8
    )
    # 减去背景标签
    patch_count = max(0, num_labels - 1)
    patch_ratio = float(strong_area / target_pixels)
    return patch_count, patch_ratio


def _normalize_heatmap(
    anomaly_map: np.ndarray,
    target_binary: np.ndarray,
    threshold: float,
) -> np.ndarray:
    """以检测阈值为锚点归一化 anomaly_map 到 [0, 1]。

    映射规则：
    - 0.0      → 完全正常（dark blue）
    - threshold → 0.5 边界（yellow/green）
    - 2*threshold → 1.0 明确异常（red）

    这样正常图像上远低于阈值的区域不会产生虚假的暖色信号，
    只有真正接近或超过阈值的区域才会在 overlay 中显示为红/黄色。
    """
    target_pixels = anomaly_map[target_binary > 0]
    if target_pixels.size == 0:
        return np.zeros_like(anomaly_map, dtype=np.float32)

    if threshold > 0:
        # 阈值锚定：threshold → 0.5
        vmax = threshold * 2.0
    else:
        # 无有效阈值时，使用目标区域 99 分位数作为参考
        vmax = float(np.percentile(target_pixels, 99.0))
        if vmax < 1e-8:
            vmax = 1.0

    normalized = anomaly_map / vmax
    return np.clip(normalized, 0.0, 1.0).astype(np.float32)
