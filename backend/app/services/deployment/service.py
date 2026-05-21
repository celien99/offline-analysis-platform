from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.logging import get_logger
from app.core.exceptions import DeploymentError, ModelNotFoundError
from app.core.security import generate_uuid
from app.models.registry import DeploymentRecord
from app.repositories.registry.deployment import DeploymentRepository
from app.repositories.registry.model_version import ModelVersionRepository

logger = get_logger(__name__)


class DeploymentService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._deployment_repo = DeploymentRepository(session)
        self._model_version_repo = ModelVersionRepository(session)

    async def deploy_model(
        self,
        model_name: str,
        version: str,
        target: str,
        deployed_by: str | None = None,
    ) -> DeploymentRecord:
        model = await self._model_version_repo.get_by_name_and_version(
            model_name, version
        )
        if model is None:
            raise ModelNotFoundError(model_name, version)

        previous_deployment = await self._deployment_repo.get_active_by_target(target)

        deployment = DeploymentRecord(
            id=generate_uuid(),
            model_version_id=model.id,
            target=target,
            deployed_by=deployed_by,
            deployed_at=datetime.now(tz=timezone.utc),
            previous_version=(
                previous_deployment.model_version_id if previous_deployment else None
            ),
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
        current = await self._deployment_repo.get_active_by_target(target)
        if current is None or current.previous_version is None:
            raise DeploymentError(
                f"No previous version to rollback for target: {target}"
            )

        prev = await self._model_version_repo.get_by_id(current.previous_version)
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
        return await self._deployment_repo.list_by_target(
            target=target, offset=offset, limit=limit
        )
