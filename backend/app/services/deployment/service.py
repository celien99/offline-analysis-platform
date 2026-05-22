from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.logging import get_logger
from app.core.config import settings
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

        # 验证模型文件存在，提前失败避免创建无效的部署记录
        if model.artifact_path is None or not Path(model.artifact_path).exists():
            raise DeploymentError(f"模型文件未找到: {model.artifact_path}")

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

        # 拷贝模型文件到部署目标目录
        self._copy_model_to_target(model.artifact_path, target)

        await self._session.flush()

        logger.info(
            "model_deployed",
            model_name=model_name,
            version=version,
            target=target,
        )
        return deployment

    @staticmethod
    def _copy_model_to_target(source_path: str, target: str) -> None:
        """将训练好的模型文件原子写入部署目标目录。"""
        target_root = settings.deploy_targets.get(target)
        if target_root is None:
            raise DeploymentError(
                f"未知部署目标: {target}。已配置目标: {list(settings.deploy_targets.keys())}"
            )

        target_dir = Path(target_root) / settings.deploy_model_subdir
        target_dir.mkdir(parents=True, exist_ok=True)

        dest = target_dir / "model.pt"
        # 原子写入：先写临时文件再 rename，避免在线系统读到不完整文件
        tmp_dest = target_dir / ".model.pt.tmp"
        shutil.copy2(source_path, str(tmp_dest))
        tmp_dest.rename(dest)

        logger.info(
            "model_file_deployed",
            source=source_path,
            destination=str(dest),
            target=target,
        )

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
