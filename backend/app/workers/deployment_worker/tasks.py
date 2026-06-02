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
    strategy: str = "immediate",
    require_gate_pass: bool = False,
) -> dict[str, object]:
    """异步执行模型部署：创建部署记录并拷贝模型文件到目标目录。"""
    logger.info(
        "deployment_task_started",
        model_name=model_name,
        version=version,
        target=target,
        strategy=strategy,
        require_gate_pass=require_gate_pass,
    )

    async def _deploy() -> dict[str, object]:
        async with async_session_factory() as session:
            service = DeploymentService(session)
            deployment = await service.deploy_model(
                model_name=model_name,
                version=version,
                target=target,
                deployed_by=deployed_by,
                strategy=strategy,
                require_gate_pass=require_gate_pass,
            )
            await session.commit()
            return {
                "status": "completed",
                "deployment_id": deployment.id,
                "target": target,
                "model_version_id": deployment.model_version_id,
                "strategy": strategy,
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


@celery_app.task(name="deployment.watch_canary_metrics")
def watch_canary_metrics(
    deployment_id: str,
    target: str,
) -> dict[str, object]:
    """金丝雀部署指标监控：达到观察周期后评估 NG 率，超阈值自动回滚。"""
    import json
    from datetime import datetime, timezone

    from app.core.config import settings
    from app.models.anomaly import AnomalyRecord
    from app.repositories.registry.deployment import DeploymentRepository
    from app.services.deployment.service import DeploymentService

    logger.info("canary_watch_started", deployment_id=deployment_id, target=target)

    async def _watch() -> dict[str, object]:
        from sqlalchemy import func, select as sa_select

        async with async_session_factory() as session:
            deployment_repo = DeploymentRepository(session)
            deployment = await deployment_repo.get_by_id(deployment_id)
            if deployment is None or deployment.canary_status != "pending_promotion":
                return {"status": "stopped", "reason": "deployment_not_active"}

            # 统计金丝雀部署后的 NG 情况
            count_stmt = sa_select(func.count()).select_from(AnomalyRecord).where(
                AnomalyRecord.deleted_at.is_(None),
                AnomalyRecord.detected_at >= deployment.deployed_at,
            )
            count_result = await session.execute(count_stmt)
            sample_count = count_result.scalar_one()

            if sample_count < settings.deploy_canary_min_samples:
                # 样本不够，重新调度
                watch_canary_metrics.apply_async(
                    kwargs={"deployment_id": deployment_id, "target": target},
                    countdown=300,
                )
                return {"status": "monitoring", "sample_count": sample_count}

            ng_stmt = sa_select(func.count()).select_from(AnomalyRecord).where(
                AnomalyRecord.deleted_at.is_(None),
                AnomalyRecord.detected_at >= deployment.deployed_at,
                AnomalyRecord.source == "patchcore",
            )
            ng_result = await session.execute(ng_stmt)
            ng_count = ng_result.scalar_one()
            ng_rate = ng_count / sample_count if sample_count > 0 else 0.0

            metrics = {
                "sample_count": sample_count,
                "ng_count": ng_count,
                "ng_rate": ng_rate,
                "checked_at": datetime.now(tz=timezone.utc).isoformat(),
            }
            deployment.canary_metrics_json = json.dumps(metrics)

            if ng_rate > settings.deploy_canary_ng_rate_threshold:
                svc = DeploymentService(session)
                await svc.rollback_canary(
                    deployment_id=deployment_id,
                    reason=f"NG rate {ng_rate:.3f} exceeds threshold {settings.deploy_canary_ng_rate_threshold}",
                )
                await session.commit()
                logger.warning("canary_auto_rollback", deployment_id=deployment_id, ng_rate=ng_rate)
                return {"status": "rolled_back", "ng_rate": ng_rate}

            await session.commit()
            logger.info("canary_healthy", deployment_id=deployment_id, ng_rate=ng_rate)
            return {"status": "healthy", "ng_rate": ng_rate, "sample_count": sample_count}

    try:
        return run_async(_watch())
    except Exception as e:
        logger.error("canary_watch_failed", deployment_id=deployment_id, error=str(e))
        return {"status": "failed", "error": str(e)}
