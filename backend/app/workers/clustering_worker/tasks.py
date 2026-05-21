from __future__ import annotations

import numpy as np

from app.common.logging import get_logger
from app.infrastructure.database.session import async_session_factory
from app.infrastructure.queue.celery_app import celery_app
from app.repositories.embedding.repository import EmbeddingRepository
from app.services.clustering.service import ClusteringService
from app.workers import run_async

logger = get_logger(__name__)


async def _run_clustering(
    min_cluster_size: int | None = None,
    min_samples: int | None = None,
    anomaly_ids: list[str] | None = None,
) -> dict[str, object]:
    async with async_session_factory() as session:
        embedding_repo = EmbeddingRepository(session)
        rows = await embedding_repo.get_all_embeddings_with_ids()

    if anomaly_ids:
        rows = [(aid, vec) for aid, vec in rows if aid in anomaly_ids]

    if len(rows) < 3:
        logger.info("clustering_skipped_too_few", count=len(rows))
        return {"status": "skipped", "reason": "too_few_embeddings", "count": len(rows)}

    embeddings: dict[str, np.ndarray] = {
        aid: np.array(vec, dtype=np.float32) for aid, vec in rows
    }

    async with async_session_factory() as session:
        service = ClusteringService(session)
        result, label_map, probability_map = await service.run_clustering(
            embeddings,
            config=None,
        )
        persisted = await service.persist_clustering_result(
            result,
            label_map=label_map,
            probability_map=probability_map,
        )

        from app.repositories.anomaly.repository import AnomalyRepository
        anomaly_repo = AnomalyRepository(session)
        for aid, label in label_map.items():
            if label >= 0:
                await anomaly_repo.update_status(aid, "clustered")

        await session.commit()

    logger.info(
        "clustering_task_complete",
        num_clusters=len(persisted),
        noise_count=result.noise_count,
        total=result.total_samples,
    )
    return {
        "status": "completed",
        "num_clusters": len(persisted),
        "noise_count": result.noise_count,
        "total_samples": result.total_samples,
    }


@celery_app.task(name="clustering.run")
def run_clustering(
    *,
    min_cluster_size: int | None = None,
    min_samples: int | None = None,
    anomaly_ids: list[str] | None = None,
) -> dict[str, object]:
    logger.info(
        "clustering_task_started",
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        anomaly_count=len(anomaly_ids) if anomaly_ids else "all",
    )
    try:
        return run_async(_run_clustering(min_cluster_size, min_samples, anomaly_ids))
    except Exception as e:
        logger.error("clustering_task_failed", error=str(e))
        return {"status": "failed", "error": str(e)}


@celery_app.task(name="clustering.schedule_regular")
def schedule_regular_clustering() -> dict[str, object]:
    logger.info("regular_clustering_scheduled")
    result = run_clustering.delay()
    return {"status": "scheduled", "task_id": result.id}
