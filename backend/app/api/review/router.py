from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.common.logging import get_logger
from app.core.security import generate_uuid
from app.models.review import ReviewRecord
from app.repositories.cluster.repository import ClusterRepository
from app.repositories.review.repository import ReviewRepository
from app.schemas.common import ErrorResponse
from app.schemas.review import ReviewResponse, ReviewSubmitRequest

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
    cluster_repo = ClusterRepository(session)
    cluster = await cluster_repo.get_by_id(request.cluster_id)
    if cluster is None:
        raise HTTPException(
            status_code=404, detail=f"Cluster {request.cluster_id} not found"
        )

    previous_status = cluster.status
    new_status = "reviewed"

    match request.action:
        case "confirm_defect":
            await cluster_repo.update_review(
                request.cluster_id,
                review_status="real_defect",
                defect_type=request.defect_type,
                reviewed_by=request.reviewer,
                name=request.new_cluster_name,
            )
        case "mark_false_alarm":
            await cluster_repo.update_review(
                request.cluster_id,
                review_status="false_alarm",
                reviewed_by=request.reviewer,
            )
        case "rename":
            await cluster_repo.update_review(
                request.cluster_id,
                review_status=cluster.review_status or "real_defect",
                reviewed_by=request.reviewer,
                name=request.new_cluster_name,
            )
        case "ignore":
            await cluster_repo.update_review(
                request.cluster_id,
                review_status="false_alarm",
                reviewed_by=request.reviewer,
            )
        case _:
            new_status = previous_status

    now = datetime.now(tz=timezone.utc)
    review_repo = ReviewRepository(session)
    review = ReviewRecord(
        id=generate_uuid(),
        cluster_id=request.cluster_id,
        reviewer=request.reviewer,
        action=request.action,
        defect_type=request.defect_type,
        comment=request.comment,
        previous_status=previous_status,
        new_status=new_status,
        reviewed_at=now,
    )
    await review_repo.create(review)

    # Auto-generate knowledge base entry from review
    if request.action in ("confirm_defect", "mark_false_alarm"):
        from app.repositories.cluster.repository import ClusterMembershipRepository
        from app.repositories.anomaly.repository import AnomalyRepository
        from app.services.knowledge import KnowledgeService

        membership_repo = ClusterMembershipRepository(session)
        anomaly_ids = await membership_repo.get_anomaly_ids_by_cluster(request.cluster_id)

        anomaly_repo = AnomalyRepository(session)
        anomalies = await anomaly_repo.get_by_ids(anomaly_ids)
        camera_ids = list({a.camera_id for a in anomalies}) if anomalies else None

        knowledge_service = KnowledgeService(session)
        await knowledge_service.auto_generate_from_review(
            cluster_id=request.cluster_id,
            review_action=request.action,
            defect_type=request.defect_type,
            camera_ids=camera_ids,
        )

    logger.info(
        "review_submitted",
        cluster_id=request.cluster_id,
        action=request.action,
        reviewer=request.reviewer,
    )

    return ReviewResponse(
        review_id=review.id,
        cluster_id=request.cluster_id,
        reviewer=request.reviewer,
        action=request.action,
        defect_type=request.defect_type,
        comment=request.comment,
        new_status=new_status,
        reviewed_at=now,
    )


@router.get(
    "/{cluster_id}/reviews",
    response_model=list[ReviewResponse],
)
async def get_cluster_reviews(
    cluster_id: str,
    session: AsyncSession = Depends(get_session),
) -> list[ReviewResponse]:
    review_repo = ReviewRepository(session)
    records = await review_repo.get_by_cluster(cluster_id)
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
