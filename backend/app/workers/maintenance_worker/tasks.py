from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, text

from app.common.logging import get_logger
from app.infrastructure.database.session import async_session_factory
from app.infrastructure.queue.celery_app import celery_app
from app.models.anomaly import AnomalyRecord
from app.models.cluster import Cluster, ClusterMembership
from app.models.embedding import EmbeddingVector
from app.models.knowledge import KnowledgeEntry, RuleEntry
from app.models.registry import DeploymentRecord, ModelVersion
from app.models.review import ReviewRecord
from app.workers import run_async

logger = get_logger(__name__)


async def _cleanup_expired(retention_days: int) -> int:
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=retention_days)
    deleted = 0

    async with async_session_factory() as session:
        models = [
            AnomalyRecord, EmbeddingVector, Cluster, ClusterMembership,
            ReviewRecord, KnowledgeEntry, RuleEntry, ModelVersion, DeploymentRecord,
        ]
        for model in models:
            stmt = delete(model).where(
                model.deleted_at.isnot(None),
                model.deleted_at < cutoff,
            )
            result = await session.execute(stmt)
            deleted += result.rowcount
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
