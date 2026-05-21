from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.common.logging import get_logger
from app.infrastructure.database.session import async_session_factory
from app.infrastructure.queue.celery_app import celery_app
from app.repositories.anomaly.repository import AnomalyRepository
from app.repositories.cluster.repository import ClusterMembershipRepository, ClusterRepository
from app.repositories.embedding.repository import EmbeddingRepository
from app.repositories.knowledge import KnowledgeRepository, RuleRepository
from app.repositories.registry.deployment import DeploymentRepository
from app.repositories.registry.model_version import ModelVersionRepository
from app.repositories.review.repository import ReviewRepository
from app.workers import run_async

logger = get_logger(__name__)


async def _cleanup_expired(retention_days: int) -> int:
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=retention_days)
    deleted = 0

    async with async_session_factory() as session:
        repos = [
            AnomalyRepository(session),
            EmbeddingRepository(session),
            ClusterRepository(session),
            ClusterMembershipRepository(session),
            ReviewRepository(session),
            KnowledgeRepository(session),
            RuleRepository(session),
            ModelVersionRepository(session),
            DeploymentRepository(session),
        ]
        for repo in repos:
            deleted += await repo.hard_delete_expired_before(cutoff)
        await session.commit()

    logger.info("maintenance_cleanup_complete", deleted_records=deleted, retention_days=retention_days)
    return deleted


@celery_app.task(name="maintenance.cleanup_expired")
def cleanup_expired_data(
    retention_days: int = 90,
) -> dict[str, object]:
    logger.info("maintenance_cleanup_started", retention_days=retention_days)
    try:
        deleted = run_async(_cleanup_expired(retention_days))
        return {"status": "completed", "deleted_records": deleted}
    except Exception as e:
        logger.error("maintenance_cleanup_failed", error=str(e))
        return {"status": "failed", "error": str(e)}


async def _reindex_embeddings() -> None:
    async with async_session_factory() as session:
        await session.execute(text("REINDEX INDEX CONCURRENTLY idx_embedding_ivfflat"))
        await session.commit()


@celery_app.task(name="maintenance.reindex_embeddings")
def reindex_embeddings() -> dict[str, object]:
    logger.info("reindex_embeddings_started")
    try:
        run_async(_reindex_embeddings())
        logger.info("reindex_embeddings_complete")
        return {"status": "completed"}
    except Exception as e:
        logger.error("reindex_embeddings_failed", error=str(e))
        return {"status": "failed", "error": str(e)}
