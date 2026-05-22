"""异步模型部署 Celery 任务。"""

from __future__ import annotations

from app.common.logging import get_logger
from app.infrastructure.database.session import async_session_factory
from app.infrastructure.queue.celery_app import celery_app
from app.services.deployment.service import DeploymentService
from app.workers import run_async

logger = get_logger(__name__)


@celery_app.task(name="deployment.deploy_model_version")
def deploy_model_version_task(
    model_name: str,
    version: str,
    target: str,
    deployed_by: str | None = None,
) -> dict[str, object]:
    """异步执行模型部署：创建部署记录并拷贝模型文件到目标目录。"""
    logger.info(
        "deployment_task_started",
        model_name=model_name,
        version=version,
        target=target,
    )

    async def _deploy() -> dict[str, object]:
        async with async_session_factory() as session:
            service = DeploymentService(session)
            deployment = await service.deploy_model(
                model_name=model_name,
                version=version,
                target=target,
                deployed_by=deployed_by,
            )
            await session.commit()
            return {
                "status": "completed",
                "deployment_id": deployment.id,
                "target": target,
                "model_version_id": deployment.model_version_id,
            }

    try:
        return run_async(_deploy())
    except Exception as e:
        logger.error(
            "deployment_task_failed",
            model_name=model_name,
            version=version,
            target=target,
            error=str(e),
        )
        return {"status": "failed", "error": str(e)}
