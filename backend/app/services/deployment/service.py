from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.logging import get_logger
from app.core.exceptions import DeploymentError, NotFoundError, ModelNotFoundError
from app.core.security import generate_uuid
from app.models.registry import DeploymentRecord, ModelVersion
from app.repositories.anomaly.repository import AnomalyRepository

logger = get_logger(__name__)


class DeploymentService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def deploy_model(
        self,
        model_name: str,
        version: str,
        target: str,
        deployed_by: str | None = None,
    ) -> DeploymentRecord:
        from sqlalchemy import select

        stmt = select(ModelVersion).where(
            ModelVersion.model_name == model_name,
            ModelVersion.version == version,
            ModelVersion.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            raise ModelNotFoundError(model_name, version)

        previous_stmt = select(DeploymentRecord).where(
            DeploymentRecord.target == target,
            DeploymentRecord.deployment_status == "active",
            DeploymentRecord.deleted_at.is_(None),
        )
        previous_result = await self._session.execute(previous_stmt)
        previous_deployment = previous_result.scalar_one_or_none()

        deployment = DeploymentRecord(
            id=generate_uuid(),
            model_version_id=model.id,
            target=target,
            deployed_by=deployed_by,
            deployed_at=datetime.now(tz=timezone.utc),
            previous_version=previous_deployment.model_version_id if previous_deployment else None,
            deployment_status="active",
        )
        self._session.add(deployment)

        if previous_deployment is not None:
            previous_deployment.deployment_status = "superseded"

        model.status = "deployed"

        await self._session.flush()
        logger.info(
            "model_deployed",
            model_name=model_name,
            version=version,
            target=target,
        )
        return deployment

    async def rollback(
        self,
        target: str,
        reason: str | None = None,
    ) -> DeploymentRecord | None:
        from sqlalchemy import select

        stmt = select(DeploymentRecord).where(
            DeploymentRecord.target == target,
            DeploymentRecord.deployment_status == "active",
            DeploymentRecord.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        current = result.scalar_one_or_none()
        if current is None or current.previous_version is None:
            raise DeploymentError(f"No previous version to rollback for target: {target}")

        previous_stmt = select(ModelVersion).where(
            ModelVersion.id == current.previous_version,
            ModelVersion.deleted_at.is_(None),
        )
        prev_model = await self._session.execute(previous_stmt)
        prev = prev_model.scalar_one_or_none()

        if prev is None:
            raise DeploymentError("Previous model version not found")

        current.deployment_status = "rolled_back"
        current.rollback_reason = reason

        deployment = DeploymentRecord(
            id=generate_uuid(),
            model_version_id=prev.id,
            target=target,
            deployed_at=datetime.now(tz=timezone.utc),
            previous_version=current.previous_version,
            deployment_status="active",
        )
        self._session.add(deployment)
        await self._session.flush()

        logger.info("model_rolled_back", target=target, reason=reason)
        return deployment

    async def list_deployments(
        self,
        target: str | None = None,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[DeploymentRecord], int]:
        from sqlalchemy import func, select

        stmt = select(DeploymentRecord).where(DeploymentRecord.deleted_at.is_(None))
        if target is not None:
            stmt = stmt.where(DeploymentRecord.target == target)
        stmt = stmt.order_by(DeploymentRecord.deployed_at.desc()).offset(offset).limit(limit)

        result = await self._session.execute(stmt)
        deployments = list(result.scalars().all())

        count_stmt = select(func.count()).select_from(DeploymentRecord).where(
            DeploymentRecord.deleted_at.is_(None)
        )
        if target is not None:
            count_stmt = count_stmt.where(DeploymentRecord.target == target)
        total = await self._session.execute(count_stmt)

        return deployments, total.scalar_one()
