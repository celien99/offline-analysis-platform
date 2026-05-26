"""模型门禁评估的 Repository。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gate import GateEvaluation
from app.repositories.base import BaseRepository


class GateEvaluationRepository(BaseRepository[GateEvaluation]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, GateEvaluation)

    async def get_latest_by_model_version(
        self, model_version_id: str
    ) -> GateEvaluation | None:
        stmt = (
            select(GateEvaluation)
            .where(
                GateEvaluation.deleted_at.is_(None),
                GateEvaluation.model_version_id == model_version_id,
            )
            .order_by(GateEvaluation.evaluated_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_passed_by_model_version(
        self, model_version_id: str
    ) -> GateEvaluation | None:
        stmt = (
            select(GateEvaluation)
            .where(
                GateEvaluation.deleted_at.is_(None),
                GateEvaluation.model_version_id == model_version_id,
                GateEvaluation.status == "passed",
            )
            .order_by(GateEvaluation.evaluated_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
