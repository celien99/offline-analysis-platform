from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.registry import ModelVersion
from app.repositories.base import BaseRepository


class ModelVersionRepository(BaseRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ModelVersion)

    async def get_by_name_and_version(
        self, model_name: str, version: str
    ) -> ModelVersion | None:
        stmt = select(ModelVersion).where(
            ModelVersion.model_name == model_name,
            ModelVersion.version == version,
            ModelVersion.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_type(
        self,
        model_type: str | None = None,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[ModelVersion], int]:
        stmt = select(ModelVersion).where(ModelVersion.deleted_at.is_(None))
        if model_type is not None:
            stmt = stmt.where(ModelVersion.model_type == model_type)
        stmt = stmt.offset(offset).limit(limit)

        result = await self._session.execute(stmt)
        models = list(result.scalars().all())

        from sqlalchemy import func

        count_stmt = (
            select(func.count())
            .select_from(ModelVersion)
            .where(ModelVersion.deleted_at.is_(None))
        )
        if model_type is not None:
            count_stmt = count_stmt.where(ModelVersion.model_type == model_type)
        total_result = await self._session.execute(count_stmt)

        return models, total_result.scalar_one()
