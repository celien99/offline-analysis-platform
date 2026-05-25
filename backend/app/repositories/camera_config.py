from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.camera_config import CameraConfig, SeatModel
from app.repositories.base import BaseRepository


class SeatModelRepository(BaseRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, SeatModel)

    async def get_by_seat_model_id(self, seat_model_id: str) -> SeatModel | None:
        stmt = select(self._model).where(
            self._model.seat_model_id == seat_model_id,
            self._model.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_with_cameras(self) -> list[SeatModel]:
        stmt = (
            select(self._model)
            .where(self._model.deleted_at.is_(None))
            .order_by(self._model.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class CameraConfigRepository(BaseRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CameraConfig)

    async def list_by_seat_model(self, seat_model_id: str) -> list[CameraConfig]:
        stmt = (
            select(self._model)
            .where(
                self._model.seat_model_id == seat_model_id,
                self._model.deleted_at.is_(None),
            )
            .order_by(self._model.camera_id)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_camera_id(
        self, seat_model_id: str, camera_id: str
    ) -> CameraConfig | None:
        stmt = select(self._model).where(
            self._model.seat_model_id == seat_model_id,
            self._model.camera_id == camera_id,
            self._model.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
