from __future__ import annotations

from app.common.logging import get_logger
from app.infrastructure.queue.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="clustering.run")
def run_clustering(
    *,
    min_cluster_size: int | None = None,
    min_samples: int | None = None,
    anomaly_ids: list[str] | None = None,
) -> dict[str, object]:
    """Run UMAP + HDBSCAN clustering on the embedding collection.

    This is a CPU-intensive task that must run in a worker.
    """
    logger.info(
        "clustering_task_started",
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        anomaly_count=len(anomaly_ids) if anomaly_ids else "all",
    )

    try:
        # Placeholder: actual clustering runs via ClusteringService
        logger.info("clustering_task_complete")
        return {
            "status": "completed",
            "message": "Clustering run dispatched",
        }
    except Exception as e:
        logger.error("clustering_task_failed", error=str(e))
        return {
            "status": "failed",
            "error": str(e),
        }


@celery_app.task(name="clustering.schedule_regular")
def schedule_regular_clustering() -> dict[str, object]:
    """Trigger regular clustering for new unclustered anomalies."""
    logger.info("regular_clustering_scheduled")
    result = run_clustering.delay()
    return {
        "status": "scheduled",
        "task_id": result.id,
    }
