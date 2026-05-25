from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.common.logging import get_logger
from app.schemas.common import ErrorResponse
from app.services.review.noise_service import NoiseReviewService

router = APIRouter(prefix="/api/anomaly", tags=["noise_review"])
logger = get_logger(__name__)


class NoiseReviewRequest(BaseModel):
    anomaly_id: str = Field(..., max_length=32)
    reviewer: str = Field(..., max_length=64)
    action: str = Field(..., pattern=r"^(confirm_defect|mark_false_alarm)$")
    defect_type: str | None = Field(
        default=None,
        pattern=r"^(wrinkle|scratch|reflection|stain|seam_shift)$",
    )
    comment: str | None = Field(default=None, max_length=2000)


@router.post(
    "/review-noise",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def review_noise_anomaly(
    request: NoiseReviewRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """审核一个无 cluster 归属的噪声异常。

    审核后会为异常创建 singleton cluster，使其进入知识的自动生成流程和
    后续的训练数据收集流程。"""
    service = NoiseReviewService(session)
    review = await service.review_noise_anomaly(
        anomaly_id=request.anomaly_id,
        reviewer=request.reviewer,
        action=request.action,
        defect_type=request.defect_type,
        comment=request.comment,
    )
    await session.commit()
    return {
        "status": "reviewed",
        "review_id": review.id,
        "anomaly_id": request.anomaly_id,
        "action": request.action,
    }
