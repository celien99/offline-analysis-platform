"""Debug artifact saving and visualization helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Tuple, Union

import cv2
import numpy as np

from ..util import build_model_scoped_root, select_texture_input, write_image

DEFAULT_DEBUG_ARTIFACT_NAMES: FrozenSet[str] = frozenset(
    {
        "overlay",
    }
)


def generate_overlay_image(
    frame_packet: Any,
    prepared: Any,
    texture_result: Optional[Any] = None,
) -> Optional[np.ndarray]:
    """Generate the BGR overlay image for one camera result.

    Returns None when no heatmap data is available (e.g. REJECT/error paths).
    """
    if prepared.roi is None or texture_result is None:
        return None
    return _overlay_heatmap_on_frame(frame_packet.image, prepared.roi, texture_result.heatmap)


def save_debug_artifacts(
    *,
    debug_dir: str,
    artifact_names: Union[List[str], Tuple[str, ...], FrozenSet[str], None] = None,
    frame_packet: Any,
    prepared: Any,
    texture_result: Optional[Any],
    seat_model_id: Optional[str],
) -> Dict[str, str]:
    """Persist the selected debug artifacts for one camera result."""
    selected_artifacts = _normalize_artifact_names(artifact_names)
    if not selected_artifacts:
        return {}

    camera_dir = (
        build_model_scoped_root(Path(debug_dir), seat_model_id)
        / frame_packet.part_id
        / frame_packet.camera_id
        / frame_packet.frame_id
    )
    camera_dir.mkdir(parents=True, exist_ok=True)
    artifact_paths: Dict[str, str] = {}

    if prepared.roi is not None and texture_result is not None:
        overlay = generate_overlay_image(
            frame_packet,
            prepared,
            texture_result=texture_result,
        )
        if overlay is not None and "overlay" in selected_artifacts:
            _save_artifact_image(
                artifact_paths,
                "overlay",
                camera_dir / "overlay.png",
                overlay,
            )

    return artifact_paths


def _normalize_artifact_names(
    artifact_names: Union[List[str], Tuple[str, ...], FrozenSet[str], None],
) -> FrozenSet[str]:
    if artifact_names is None:
        return DEFAULT_DEBUG_ARTIFACT_NAMES
    requested = [str(name).strip() for name in artifact_names if str(name).strip()]
    unexpected = sorted(set(requested) - DEFAULT_DEBUG_ARTIFACT_NAMES)
    if unexpected:
        formatted = ", ".join(f"`{item}`" for item in unexpected)
        raise ValueError(f"debug_artifact_names 包含不支持的调试产物: {formatted}")
    return frozenset(requested)


def _save_artifact_image(
    artifact_paths: Dict[str, str],
    key: str,
    path: Path,
    image: Optional[Any],
) -> None:
    """Write one final per-camera artifact."""
    if image is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    write_image(path, image)
    artifact_paths[key] = str(path)


def _overlay_heatmap_on_frame(
    frame_image: Any,
    roi,
    heatmap: np.ndarray,
) -> np.ndarray:
    """Overlay a canonical ROI heatmap back onto the original frame size."""
    frame_base = _ensure_color_image(frame_image)
    x1, y1, x2, y2 = _box_to_frame_pixels(roi.crop_box, frame_base.shape[:2])
    if x2 <= x1 or y2 <= y1:
        return frame_base

    crop_base = frame_base[y1:y2, x1:x2]
    crop_heatmap = _restore_heatmap_to_crop(roi, heatmap, crop_base.shape[:2])
    frame_base[y1:y2, x1:x2] = _overlay_heatmap(crop_base, crop_heatmap)
    return frame_base


def _restore_heatmap_to_crop(
    roi,
    heatmap: np.ndarray,
    crop_shape: Tuple[int, int],
) -> np.ndarray:
    """Map canonical heatmap (direct-stretch resized) back to original crop dimensions.

    Since _letterbox_bundle now uses direct stretch (matching training),
    the heatmap maps 1:1 from canonical_size → crop_shape via simple resize.
    """
    canonical_shape = select_texture_input(roi).shape[:2]
    clipped = np.clip(np.asarray(heatmap, dtype=np.float32), 0.0, 1.0)
    if clipped.shape != canonical_shape:
        clipped = cv2.resize(
            clipped,
            (canonical_shape[1], canonical_shape[0]),
            interpolation=cv2.INTER_LINEAR,
        )

    crop_height, crop_width = crop_shape
    if crop_height <= 0 or crop_width <= 0:
        return np.zeros((0, 0), dtype=np.float32)

    return cv2.resize(
        clipped,
        (crop_width, crop_height),
        interpolation=cv2.INTER_LINEAR,
    )


def _box_to_frame_pixels(box, frame_shape: Tuple[int, int]) -> Tuple[int, int, int, int]:
    height, width = frame_shape
    x1 = int(round(float(box.x1)))
    y1 = int(round(float(box.y1)))
    x2 = int(round(float(box.x2)))
    y2 = int(round(float(box.y2)))
    return (
        min(max(x1, 0), width),
        min(max(y1, 0), height),
        min(max(x2, 0), width),
        min(max(y2, 0), height),
    )


def _overlay_heatmap(
    image: Any,
    heatmap: np.ndarray,
    *,
    peak_low_percentile: float = 70.0,
    peak_high_percentile: float = 99.5,
    base_emphasis_weight: float = 0.35,
    dilate_kernel_size: int = 5,
    peak_mask_threshold: float = 0.92,
    alpha_base: float = 0.15,
    alpha_scale: float = 0.85,
    alpha_max: float = 0.95,
) -> np.ndarray:
    """将热力图叠加到 ROI 图像上，保留冷色区域的原始图像可见性。

    两段归一化已把正常区域压缩到 [0, 0.3]，异常区域展开到 [0.3, 1.0]，
    因此不再需要 gamma 校正来抑制低值噪声。叠加前会增强峰值并膨胀热点，
    确保小面积缺陷在上采样到原图分辨率后仍然清晰可见。

    Args:
        image: 原始 ROI 图像 (H, W, 3) BGR uint8。
        heatmap: 归一化后的热力图 (H, W) float32 [0, 1]。
        peak_low_percentile: 峰值增强的低分位截断点（抑制背景噪声）。
        peak_high_percentile: 峰值增强的高分位截断点（防止单像素极值拉伸）。
        base_emphasis_weight: 原始 clipped 值在 emphasized 混合中的权重。
            越高越保留全局响应，越低越依赖分位增强。0.35 兼顾两者。
        dilate_kernel_size: 膨胀核尺寸（px），小面积缺陷需要较大核保证可见性。
        peak_mask_threshold: 白色热点标记阈值，≥此值的热力像素显示为白色。
        alpha_base: alpha 合成的基础透明度，保证低响应区域也有微弱叠加。
        alpha_scale: alpha 合成的热力权重系数。
        alpha_max: alpha 合成的透明度上限，保留下方图像可见性。
    """
    base_image, clipped = _prepare_heatmap_layers(image, heatmap)
    if float(clipped.max()) <= 1e-6:
        return base_image

    # 强化峰值热点：先用高分位截断抑制低响应铺底，再膨胀高响应区域。
    # 明显缺陷点即便面积很小，也会在 overlay 中形成清晰红/白热点。
    positive = clipped[clipped > 1e-6]
    if positive.size:
        low = float(np.percentile(positive, peak_low_percentile))
        high = float(np.percentile(positive, peak_high_percentile))
        if high <= low + 1e-6:
            high = float(positive.max())
        if high > low + 1e-6:
            emphasized = np.clip((clipped - low) / (high - low), 0.0, 1.0)
        else:
            emphasized = clipped.copy()
    else:
        emphasized = clipped.copy()
    emphasized = np.maximum(clipped * base_emphasis_weight, emphasized)

    kernel = np.ones((dilate_kernel_size, dilate_kernel_size), dtype=np.uint8)
    dilated = cv2.dilate(emphasized, kernel, iterations=1)

    color_map = cv2.applyColorMap(np.uint8(dilated * 255), cv2.COLORMAP_JET).astype(np.float32)
    peak_mask = dilated >= peak_mask_threshold
    color_map[peak_mask] = np.array([255.0, 255.0, 255.0], dtype=np.float32)
    base_float = base_image.astype(np.float32)
    alpha = np.clip(alpha_base + dilated[..., None] * alpha_scale, 0.0, alpha_max)
    overlay = base_float * (1.0 - alpha) + color_map * alpha
    return np.clip(overlay, 0.0, 255.0).astype(np.uint8)


def _prepare_heatmap_layers(
    image: Any,
    heatmap: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """Normalize heatmap geometry and value range for visualization helpers."""
    base_image = _ensure_color_image(image)
    clipped = np.clip(np.asarray(heatmap, dtype=np.float32), 0.0, 1.0)
    if clipped.shape != base_image.shape[:2]:
        clipped = cv2.resize(
            clipped,
            (base_image.shape[1], base_image.shape[0]),
            interpolation=cv2.INTER_LINEAR,
        )
    return base_image, clipped


def _ensure_color_image(image: Any) -> np.ndarray:
    """Ensure the heatmap base is a BGR image."""
    array = np.asarray(image)
    if array.ndim == 2:
        return cv2.cvtColor(array, cv2.COLOR_GRAY2BGR)
    if array.ndim == 3 and array.shape[2] == 4:
        return cv2.cvtColor(array, cv2.COLOR_BGRA2BGR)
    return array.copy()
