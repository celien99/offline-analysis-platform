from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.camera_config import CameraConfig, SeatModel
from app.repositories.base import BaseRepository


class SeatModelRepository(BaseRepository[SeatModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, SeatModel)

    async def get_by_seat_model_id(self, seat_model_id: str) -> SeatModel | None:
        stmt = select(SeatModel).where(
            SeatModel.seat_model_id == seat_model_id,
            SeatModel.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_with_cameras(self) -> Sequence[SeatModel]:
        stmt = (
            select(SeatModel)
            .where(SeatModel.deleted_at.is_(None))
            .order_by(SeatModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()


class CameraConfigRepository(BaseRepository[CameraConfig]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CameraConfig)

    async def list_by_seat_model(self, seat_model_id: str) -> Sequence[CameraConfig]:
        stmt = (
            select(CameraConfig)
            .where(
                CameraConfig.seat_model_id == seat_model_id,
                CameraConfig.deleted_at.is_(None),
            )
            .order_by(CameraConfig.camera_id)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_by_camera_id(
        self, seat_model_id: str, camera_id: str
    ) -> CameraConfig | None:
        stmt = select(CameraConfig).where(
            CameraConfig.seat_model_id == seat_model_id,
            CameraConfig.camera_id == camera_id,
            CameraConfig.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
