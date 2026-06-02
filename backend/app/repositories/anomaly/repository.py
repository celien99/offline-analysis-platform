from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.anomaly import AnomalyRecord
from app.repositories.base import BaseRepository


class AnomalyRepository(BaseRepository[AnomalyRecord]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AnomalyRecord)

    async def get_by_camera_and_date(
        self,
        camera_id: str,
        date_folder: str,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> Sequence[AnomalyRecord]:
        stmt = (
            select(AnomalyRecord)
            .where(
                AnomalyRecord.deleted_at.is_(None),
                AnomalyRecord.camera_id == camera_id,
                AnomalyRecord.date_folder == date_folder,
            )
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_by_status(
        self,
        status: str,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> Sequence[AnomalyRecord]:
        return await self.list_all(status=status, offset=offset, limit=limit)

    async def get_unprocessed(
        self, *, limit: int = 100
    ) -> Sequence[AnomalyRecord]:
        stmt = (
            select(AnomalyRecord)
            .where(
                AnomalyRecord.deleted_at.is_(None),
                AnomalyRecord.status == "pending",
            )
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def update_status(self, anomaly_id: str, status: str) -> None:
        stmt = (
            update(AnomalyRecord)
            .where(AnomalyRecord.id == anomaly_id)
            .values(status=status)
        )
        await self._session.execute(stmt)

    async def update_heatmap_path(self, anomaly_id: str, heatmap_path: str) -> None:
        stmt = (
            update(AnomalyRecord)
            .where(AnomalyRecord.id == anomaly_id)
            .values(heatmap_path=heatmap_path)
        )
        await self._session.execute(stmt)

    async def get_noise_anomalies(
        self, *, offset: int = 0, limit: int = 100,
        seat_model_id: str | None = None,
        camera_id: str | None = None,
        region_id: str | None = None,
    ) -> Sequence[AnomalyRecord]:
        """返回 status='noise' 且未归属任何 cluster 的噪声异常。"""
        from app.models.cluster import ClusterMembership

        subq = select(ClusterMembership.anomaly_id).where(
            ClusterMembership.deleted_at.is_(None)
        )
        conditions = [
            AnomalyRecord.deleted_at.is_(None),
            AnomalyRecord.status == "noise",
            AnomalyRecord.id.notin_(subq),
        ]
        if seat_model_id:
            conditions.append(AnomalyRecord.seat_model_id == seat_model_id)
        if camera_id:
            conditions.append(AnomalyRecord.camera_id == camera_id)
        if region_id:
            conditions.append(AnomalyRecord.region_id == region_id)
        stmt = (
            select(AnomalyRecord)
            .where(*conditions)
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def count_noise_anomalies(
        self, seat_model_id: str | None = None,
        camera_id: str | None = None,
        region_id: str | None = None,
    ) -> int:
        """统计未归属任何 cluster 的 noise 异常数。"""
        from app.models.cluster import ClusterMembership

        subq = select(ClusterMembership.anomaly_id).where(
            ClusterMembership.deleted_at.is_(None)
        )
        conditions = [
            AnomalyRecord.deleted_at.is_(None),
            AnomalyRecord.status == "noise",
            AnomalyRecord.id.notin_(subq),
        ]
        if seat_model_id:
            conditions.append(AnomalyRecord.seat_model_id == seat_model_id)
        if camera_id:
            conditions.append(AnomalyRecord.camera_id == camera_id)
        if region_id:
            conditions.append(AnomalyRecord.region_id == region_id)
        stmt = (
            select(func.count())
            .select_from(AnomalyRecord)
            .where(*conditions)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def get_by_ids(
        self, ids: list[str]
    ) -> Sequence[AnomalyRecord]:
        if not ids:
            return []
        stmt = select(AnomalyRecord).where(
            AnomalyRecord.deleted_at.is_(None),
            AnomalyRecord.id.in_(ids),
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_filter_stats(
        self,
        since: datetime | None = None,
        camera_id: str | None = None,
        seat_model_id: str | None = None,
        region_id: str | None = None,
    ) -> dict[str, int]:
        """统计指定时间范围内的 filter_action 分布。"""
        conditions = [
            AnomalyRecord.deleted_at.is_(None),
            AnomalyRecord.filter_action.isnot(None),
        ]
        if since is not None:
            conditions.append(AnomalyRecord.detected_at >= since)
        if camera_id:
            conditions.append(AnomalyRecord.camera_id == camera_id)
        if seat_model_id:
            conditions.append(AnomalyRecord.seat_model_id == seat_model_id)
        if region_id:
            conditions.append(AnomalyRecord.region_id == region_id)
        stmt = (
            select(AnomalyRecord.filter_action, func.count(AnomalyRecord.id))
            .where(*conditions)
            .group_by(AnomalyRecord.filter_action)
        )
        result = await self._session.execute(stmt)
        return dict(result.all())

    async def get_filter_vs_human_review(
        self,
        since: datetime | None = None,
        camera_id: str | None = None,
        seat_model_id: str | None = None,
        region_id: str | None = None,
    ) -> list[dict[str, object]]:
        """交叉对比 filter_action 与人工审核结果。"""
        from app.models.cluster import Cluster, ClusterMembership

        conditions = [
            AnomalyRecord.deleted_at.is_(None),
            AnomalyRecord.filter_action.isnot(None),
            Cluster.review_status.isnot(None),
            Cluster.deleted_at.is_(None),
            ClusterMembership.deleted_at.is_(None),
        ]
        if since is not None:
            conditions.append(AnomalyRecord.detected_at >= since)
        if camera_id:
            conditions.append(AnomalyRecord.camera_id == camera_id)
        if seat_model_id:
            conditions.append(AnomalyRecord.seat_model_id == seat_model_id)
        if region_id:
            conditions.append(AnomalyRecord.region_id == region_id)

        stmt = (
            select(
                AnomalyRecord.filter_action,
                Cluster.review_status,
                func.count(AnomalyRecord.id),
            )
            .join(ClusterMembership, ClusterMembership.anomaly_id == AnomalyRecord.id)
            .join(Cluster, Cluster.id == ClusterMembership.cluster_id)
            .where(*conditions)
            .group_by(AnomalyRecord.filter_action, Cluster.review_status)
        )
        result = await self._session.execute(stmt)
        return [
            {"filter_action": row[0], "human_review": row[1], "count": row[2]}
            for row in result.all()
        ]
