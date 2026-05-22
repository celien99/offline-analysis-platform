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

from .types import CameraInspectionResult, InspectionResponse


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

    # ROI 裁剪图
    if result.overlay_image is not None:
        roi_bytes = _encode_bgr_image(result.overlay_image, ".jpg")
        files["roi_file"] = ("roi.jpg", roi_bytes, "image/jpeg")

    # 热力图叠加图也作为 original 上传
    if result.overlay_image is not None:
        files["original_file"] = ("overlay.jpg", _encode_bgr_image(result.overlay_image, ".jpg"), "image/jpeg")

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


def _encode_bgr_image(image: np.ndarray, ext: str = ".jpg") -> bytes:
    """将 BGR numpy 图像编码为 JPEG/PNG 字节。"""
    success, encoded = cv2.imencode(ext, image)
    if not success:
        raise ValueError("图像编码失败")
    return encoded.tobytes()


__all__ = [
    "upload_camera_result",
    "upload_inspection_response",
]
