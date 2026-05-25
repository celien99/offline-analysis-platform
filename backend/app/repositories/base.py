from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.base import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    def __init__(self, session: AsyncSession, model: type[T]) -> None:
        self._session = session
        self._model = model

    async def get_by_id(self, id_: str) -> T | None:
        stmt = select(self._model).where(
            self._model.id == id_,  # type: ignore[attr-defined]
            self._model.deleted_at.is_(None),  # type: ignore[attr-defined]
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        **filters: object,
    ) -> Sequence[T]:
        stmt = select(self._model).where(self._model.deleted_at.is_(None))  # type: ignore[attr-defined]
        for key, value in filters.items():
            if value is not None:
                stmt = stmt.where(getattr(self._model, key) == value)
        stmt = stmt.offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def count(self, **filters: object) -> int:
        stmt = select(func.count()).select_from(self._model).where(
            self._model.deleted_at.is_(None)  # type: ignore[attr-defined]
        )
        for key, value in filters.items():
            if value is not None:
                stmt = stmt.where(getattr(self._model, key) == value)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def create(self, entity: T) -> T:
        self._session.add(entity)
        await self._session.flush()
        return entity

    async def create_all(self, entities: list[T]) -> list[T]:
        self._session.add_all(entities)
        await self._session.flush()
        return entities

    async def update(self, entity: T) -> T:
        await self._session.flush()
        return entity

    async def soft_delete(self, id_: str) -> None:
        entity = await self.get_by_id(id_)
        if entity is not None:
            from datetime import datetime, timezone

            entity.deleted_at = datetime.now(tz=timezone.utc)  # type: ignore[attr-defined]
            await self._session.flush()

    async def hard_delete_expired_before(self, cutoff: datetime) -> int:
        from sqlalchemy import delete

        stmt = delete(self._model).where(
            self._model.deleted_at.isnot(None),  # type: ignore[attr-defined]
            self._model.deleted_at < cutoff,  # type: ignore[attr-defined]
        )
        result = await self._session.execute(stmt)
        return result.rowcount  # type: ignore[no-any-return, attr-defined]
