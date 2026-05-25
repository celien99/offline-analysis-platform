from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.registry import DeploymentRecord
from app.repositories.base import BaseRepository


class DeploymentRepository(BaseRepository[DeploymentRecord]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, DeploymentRecord)

    async def get_active_by_target(
        self, target: str
    ) -> DeploymentRecord | None:
        stmt = select(DeploymentRecord).where(
            DeploymentRecord.target == target,
            DeploymentRecord.deployment_status == "active",
            DeploymentRecord.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, deployment_id: str) -> DeploymentRecord | None:
        """按主键查询部署记录。"""
        stmt = select(DeploymentRecord).where(
            DeploymentRecord.id == deployment_id,
            DeploymentRecord.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_canary(self, target: str) -> DeploymentRecord | None:
        """查询指定目标上待推广的金丝雀部署。"""
        stmt = (
            select(DeploymentRecord)
            .where(
                DeploymentRecord.deleted_at.is_(None),
                DeploymentRecord.target == target,
                DeploymentRecord.strategy == "canary",
                DeploymentRecord.deployment_status == "active",
                DeploymentRecord.canary_status == "pending_promotion",
            )
            .order_by(DeploymentRecord.deployed_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_target(
        self,
        target: str | None = None,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[DeploymentRecord], int]:
        stmt = select(DeploymentRecord).where(
            DeploymentRecord.deleted_at.is_(None)
        )
        if target is not None:
            stmt = stmt.where(DeploymentRecord.target == target)
        stmt = stmt.order_by(DeploymentRecord.deployed_at.desc()).offset(offset).limit(limit)

        result = await self._session.execute(stmt)
        deployments = list(result.scalars().all())

        count_stmt = (
            select(func.count())
            .select_from(DeploymentRecord)
            .where(DeploymentRecord.deleted_at.is_(None))
        )
        if target is not None:
            count_stmt = count_stmt.where(DeploymentRecord.target == target)
        total_result = await self._session.execute(count_stmt)

        return deployments, total_result.scalar_one()
