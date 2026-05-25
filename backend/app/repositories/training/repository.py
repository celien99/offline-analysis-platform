from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.training import TrainingRun
from app.repositories.base import BaseRepository


class TrainingRunRepository(BaseRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TrainingRun)

    async def get_latest_full_train(self) -> TrainingRun | None:
        """返回最近一次非删除的完整训练记录。"""
        stmt = (
            select(TrainingRun)
            .where(
                TrainingRun.deleted_at.is_(None),
            )
            .order_by(TrainingRun.started_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_train(self) -> TrainingRun | None:
        """返回最近一次非删除的训练记录（不限类型）。"""
        stmt = (
            select(TrainingRun)
            .where(
                TrainingRun.deleted_at.is_(None),
            )
            .order_by(TrainingRun.started_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_reviewed_clusters_since(self, since: datetime) -> int:
        """统计自 since 以来审核的 cluster 数（用于自动训练判断）。"""
        from app.models.cluster import Cluster

        stmt = (
            select(func.count())
            .select_from(Cluster)
            .where(
                Cluster.deleted_at.is_(None),
                Cluster.status == "reviewed",
                Cluster.review_status.isnot(None),
                Cluster.reviewed_at >= since,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()
