from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.logging import get_logger
from app.core.exceptions import NotFoundError, ValidationError
from app.core.security import generate_uuid
from app.models.anomaly import AnomalyRecord
from app.models.anomaly_review import AnomalyReview
from app.models.cluster import Cluster, ClusterMembership
from app.repositories.anomaly.repository import AnomalyRepository
from app.repositories.base import BaseRepository
from app.repositories.cluster.repository import ClusterMembershipRepository, ClusterRepository

logger = get_logger(__name__)


class AnomalyReviewRepository(BaseRepository):
    """噪声异常审核记录的 Repository。"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AnomalyReview)


class NoiseReviewService:
    """处理无 cluster 归属的噪声异常审核。

    噪声异常（HDBSCAN label=-1）不会创建 cluster，因此无法通过常规的
    cluster review 流程处理。本 service 为每个被审核的噪声异常创建一个
    singleton cluster，使其可以进入后续的知识生成和训练数据收集流程。
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._anomaly_repo = AnomalyRepository(session)
        self._anomaly_review_repo = AnomalyReviewRepository(session)
        self._cluster_repo = ClusterRepository(session)
        self._membership_repo = ClusterMembershipRepository(session)

    async def list_noise_anomalies(
        self, *, offset: int = 0, limit: int = 100,
        seat_model_id: str | None = None,
        camera_id: str | None = None,
        region_id: str | None = None,
    ) -> tuple[list[AnomalyRecord], int]:
        records = await self._anomaly_repo.get_noise_anomalies(
            offset=offset, limit=limit,
            seat_model_id=seat_model_id,
            camera_id=camera_id,
            region_id=region_id,
        )
        total = await self._anomaly_repo.count_noise_anomalies(
            seat_model_id=seat_model_id,
            camera_id=camera_id,
            region_id=region_id,
        )
        return list(records), total

    async def review_noise_anomaly(
        self,
        *,
        anomaly_id: str,
        reviewer: str,
        action: str,
        defect_type: str | None = None,
        comment: str | None = None,
    ) -> AnomalyReview:
        if action not in ("confirm_defect", "mark_false_alarm"):
            raise ValidationError(
                f"Invalid action: {action}",
                code="INVALID_ACTION",
            )

        anomaly = await self._anomaly_repo.get_by_id(anomaly_id)
        if anomaly is None:
            raise NotFoundError("Anomaly", anomaly_id)

        review_status = "real_defect" if action == "confirm_defect" else "false_alarm"

        # 创建 singleton cluster 使其可被训练数据收集
        cluster_id = generate_uuid()
        cluster = Cluster(
            id=cluster_id,
            seat_model_id=anomaly.seat_model_id,
            name=f"noise_{anomaly_id[:8]}",
            sample_count=1,
            status="reviewed",
            review_status=review_status,
            defect_type=defect_type,
            reviewed_by=reviewer,
            hdbscan_label=-1,
            clustering_run_at=datetime.now(tz=timezone.utc),
            reviewed_at=datetime.now(tz=timezone.utc),
        )
        await self._cluster_repo.create(cluster)

        # 建立 cluster → anomaly 归属
        membership = ClusterMembership(
            id=generate_uuid(),
            cluster_id=cluster_id,
            anomaly_id=anomaly_id,
        )
        self._session.add(membership)

        # 更新异常状态
        await self._anomaly_repo.update_status(anomaly_id, "reviewed")

        # 创建审核记录
        review = AnomalyReview(
            id=generate_uuid(),
            anomaly_id=anomaly_id,
            reviewer=reviewer,
            action=action,
            defect_type=defect_type,
            comment=comment,
            reviewed_at=datetime.now(tz=timezone.utc),
        )
        await self._anomaly_review_repo.create(review)

        # 自动生成知识条目（复用 ReviewService 的内部方法）
        from app.services.review.service import ReviewService

        review_svc = ReviewService(self._session)
        await review_svc._auto_generate_knowledge(
            cluster_id=cluster_id,
            review_action=action,
            defect_type=defect_type,
        )

        logger.info(
            "noise_anomaly_reviewed",
            anomaly_id=anomaly_id,
            cluster_id=cluster_id,
            action=action,
        )
        return review
