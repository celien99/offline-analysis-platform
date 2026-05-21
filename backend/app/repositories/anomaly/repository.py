from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.anomaly import AnomalyRecord
from app.repositories.base import BaseRepository


class AnomalyRepository(BaseRepository):
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

    async def get_by_ids(
        self, ids: list[str]
    ) -> Sequence[AnomalyRecord]:
        stmt = select(AnomalyRecord).where(
            AnomalyRecord.deleted_at.is_(None),
            AnomalyRecord.id.in_(ids),
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
