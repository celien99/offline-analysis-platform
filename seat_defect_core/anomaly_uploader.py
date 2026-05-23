"""将 seat_defect_core 检测结果上传到离线分析平台。

此模块填补在线→离线数据闭环的关键缺口：
将实时检测中发现的异常（NG 结果）及其关联图片（ROI、热力图等）
上传到后端 API，供后续 embedding 提取、聚类分析和分类器训练使用。
"""

from __future__ import annotations

import base64
import io
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
import requests

from .core_types import CameraInspectionResult, InspectionResponse


def upload_camera_result(
    result: CameraInspectionResult,
    base_url: str,
    *,
    date_folder: Optional[str] = None,
    timeout: float = 30.0,
) -> Optional[Dict[str, Any]]:
    """将单机位 NG 检测结果上传到离线平台。

    Args:
        result: 单机位检测结果（仅 status=="NG" 的会上传）。
        base_url: 后端 API 基础地址，如 "http://localhost:8000"。
        date_folder: 日期文件夹名，默认用当天日期 YYYY-MM-DD。
        timeout: HTTP 请求超时秒数。

    Returns:
        后端返回的 JSON 响应，包含 anomaly_id；非 NG 或无有效数据时返回 None。
    """
    if result.status != "NG":
        return None

    if date_folder is None:
        date_folder = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

    files: Dict[str, tuple] = {}
    data: Dict[str, Any] = {
        "camera_id": result.camera_id,
        "source": "patchcore",
        "date_folder": date_folder,
        "detected_at": datetime.now(tz=timezone.utc).isoformat(),
    }

    # 异常分数
    if result.texture_result is not None:
        data["anomaly_score"] = float(result.texture_result.score)
    elif result.region_results:
        # 区域模式下从 region_results 收集最高异常分数
        region_scores = [
            r.texture_result.score
            for r in result.region_results
            if r.texture_result is not None
        ]
        if region_scores:
            data["anomaly_score"] = float(max(region_scores))

    # 原图：用户/产线上传到 inspection 的原始大图，不含热力图叠加。
    if result.original_image is not None:
        files["original_file"] = (
            "original.jpg",
            _encode_bgr_image(result.original_image, ".jpg"),
            "image/jpeg",
        )

    # ROI：原图坐标系下的感兴趣区域裁剪，保留原始 ROI 形状。
    if result.roi_image is not None:
        files["roi_file"] = ("roi.jpg", _encode_bgr_image(result.roi_image, ".jpg"), "image/jpeg")

    # Crop：供离线平台 embedding 提取使用的 ROI 裁剪图。
    # 优先使用 roi_aligned_image（标准化尺寸），回退到 roi_image。
    crop_img = (
        result.roi_aligned_image
        if result.roi_aligned_image is not None
        else result.roi_image
    )
    if crop_img is not None:
        files["crop_file"] = ("crop.jpg", _encode_bgr_image(crop_img, ".jpg"), "image/jpeg")

    # Heatmap：Inspection 页面输出的检测叠加图。它已经把完整 ROI 或 region
    # PatchCore 的热力图统一映射回原图坐标系。
    if result.overlay_image is not None:
        files["heatmap_file"] = (
            "heatmap.jpg",
            _encode_bgr_image(result.overlay_image, ".jpg"),
            "image/jpeg",
        )
    else:
        heatmap = _extract_heatmap_for_upload(result)
        if heatmap is not None:
            files["heatmap_file"] = ("heatmap.png", _encode_heatmap(heatmap), "image/png")

    try:
        url = f"{base_url.rstrip('/')}/api/anomaly/upload-with-files"
        response = requests.post(
            url,
            data=data,
            files=files,
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None


def upload_inspection_response(
    response: InspectionResponse,
    base_url: str,
    *,
    date_folder: Optional[str] = None,
    timeout: float = 30.0,
) -> List[Dict[str, Any]]:
    """遍历 InspectionResponse 中的所有相机结果，上传每个 NG 到离线平台。

    Args:
        response: 整件检测响应。
        base_url: 后端 API 基础地址。
        date_folder: 日期文件夹名。
        timeout: HTTP 请求超时秒数。

    Returns:
        成功上传的异常记录列表（每项包含 backend 返回的 anomaly_id）。
    """
    results: List[Dict[str, Any]] = []
    for camera_result in response.result.camera_results:
        uploaded = upload_camera_result(
            camera_result,
            base_url,
            date_folder=date_folder,
            timeout=timeout,
        )
        if uploaded is not None:
            results.append(uploaded)
    return results


def _extract_heatmap_for_upload(result: CameraInspectionResult) -> np.ndarray | None:
    """从检测结果中提取原始热力图，作为无 overlay 时的兼容兜底。"""
    if result.texture_result is not None and result.texture_result.heatmap is not None:
        return result.texture_result.heatmap
    return None


def _encode_heatmap(heatmap: np.ndarray) -> bytes:
    """将 2D 热力图 float 数组编码为伪彩色 PNG。"""
    normalized = np.zeros_like(heatmap, dtype=np.float32)
    h_min = float(heatmap.min())
    h_max = float(heatmap.max())
    if h_max - h_min > 1e-8:
        normalized = ((heatmap - h_min) / (h_max - h_min) * 255).astype(np.uint8)
    else:
        normalized = np.zeros_like(heatmap, dtype=np.uint8)
    colored = cv2.applyColorMap(normalized, cv2.COLORMAP_JET)
    success, encoded = cv2.imencode(".png", colored)
    if not success:
        raise ValueError("热力图编码失败")
    return encoded.tobytes()


def _encode_bgr_image(image: np.ndarray, ext: str = ".jpg") -> bytes:
    """将 BGR numpy 图像编码为 JPEG/PNG 字节。"""
    normalized = _normalize_bgr_image(image)
    success, encoded = cv2.imencode(ext, normalized)
    if not success:
        raise ValueError("图像编码失败")
    return encoded.tobytes()


def _normalize_bgr_image(image: np.ndarray) -> np.ndarray:
    """Normalize grayscale/BGRA arrays to BGR before storage."""
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.ndim == 3 and image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    return image


__all__ = [
    "upload_camera_result",
    "upload_inspection_response",
]
