from __future__ import annotations

from pydantic import BaseModel


class CameraInspectionResultSchema(BaseModel):
    """单相机检测结果。"""

    camera_id: str
    status: str  # OK / NG / REJECT / MISSING
    anomaly_score: float | None = None
    threshold: float | None = None
    is_anomaly: bool | None = None
    decision_reason: str | None = None
    error_message: str | None = None
    overlay_image_base64: str | None = None  # 检测叠加图 (JPEG Base64)


class InspectionResultResponse(BaseModel):
    """检测结果完整响应。"""

    task_id: str
    status: str  # PENDING / STARTED / SUCCESS / FAILURE
    overall_status: str | None = None  # OK / NG / REJECT
    decision_reason: str | None = None
    camera_results: list[CameraInspectionResultSchema] = []
    error_message: str | None = None
    created_at: str | None = None
