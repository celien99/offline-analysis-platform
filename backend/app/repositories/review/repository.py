from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.review import ReviewRecord
from app.repositories.base import BaseRepository


class ReviewRepository(BaseRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ReviewRecord)

    async def get_by_cluster(
        self,
        cluster_id: str,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> Sequence[ReviewRecord]:
        stmt = (
            select(ReviewRecord)
            .where(
                ReviewRecord.deleted_at.is_(None),
                ReviewRecord.cluster_id == cluster_id,
            )
            .order_by(ReviewRecord.reviewed_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_by_reviewer(
        self,
        reviewer: str,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> Sequence[ReviewRecord]:
        stmt = (
            select(ReviewRecord)
            .where(
                ReviewRecord.deleted_at.is_(None),
                ReviewRecord.reviewer == reviewer,
            )
            .order_by(ReviewRecord.reviewed_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_latest_review(self, cluster_id: str) -> ReviewRecord | None:
        stmt = (
            select(ReviewRecord)
            .where(
                ReviewRecord.deleted_at.is_(None),
                ReviewRecord.cluster_id == cluster_id,
            )
            .order_by(ReviewRecord.reviewed_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
