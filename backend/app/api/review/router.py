from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.common.logging import get_logger
from app.schemas.common import ErrorResponse
from app.schemas.review import ReviewResponse, ReviewSubmitRequest
from app.services.review import ReviewService

router = APIRouter(prefix="/api/cluster", tags=["review"])
logger = get_logger(__name__)


@router.post(
    "/review",
    response_model=ReviewResponse,
    responses={404: {"model": ErrorResponse}},
)
async def submit_review(
    request: ReviewSubmitRequest,
    session: AsyncSession = Depends(get_session),
) -> ReviewResponse:
    service = ReviewService(session)
    review = await service.submit_review(
        cluster_id=request.cluster_id,
        reviewer=request.reviewer,
        action=request.action,
        defect_type=request.defect_type,
        comment=request.comment,
        new_cluster_name=request.new_cluster_name,
        merge_source_ids=request.merge_source_ids,
        split_member_ids=request.split_member_ids,
    )
    return ReviewResponse(
        review_id=review.id,
        cluster_id=review.cluster_id,
        reviewer=review.reviewer,
        action=review.action,
        defect_type=review.defect_type,
        comment=review.comment,
        new_status=review.new_status,
        reviewed_at=review.reviewed_at,
    )


@router.get(
    "/{cluster_id}/reviews",
    response_model=list[ReviewResponse],
)
async def get_cluster_reviews(
    cluster_id: str,
    session: AsyncSession = Depends(get_session),
) -> list[ReviewResponse]:
    service = ReviewService(session)
    records = await service.get_cluster_reviews(cluster_id)
    return [
        ReviewResponse(
            review_id=r.id,
            cluster_id=r.cluster_id,
            reviewer=r.reviewer,
            action=r.action,
            defect_type=r.defect_type,
            comment=r.comment,
            new_status=r.new_status,
            reviewed_at=r.reviewed_at,
        )
        for r in records
    ]
