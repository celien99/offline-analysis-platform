from __future__ import annotations

from app.common.logging import get_logger
from app.infrastructure.queue.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="thumbnail.generate")
def generate_thumbnail(
    anomaly_id: str,
    source_path: str,
    size: tuple[int, int] = (256, 256),
) -> dict[str, object]:
    """Generate thumbnail for anomaly image browsing.

    Lightweight CPU task, offloaded to avoid blocking the API loop.
    """
    logger.info("thumbnail_task_started", anomaly_id=anomaly_id, size=size)

    try:
        # Placeholder: actual thumbnail generation via Pillow
        logger.info("thumbnail_task_complete", anomaly_id=anomaly_id)
        return {
            "status": "completed",
            "anomaly_id": anomaly_id,
            "thumbnail_path": None,
        }
    except Exception as e:
        logger.error("thumbnail_task_failed", anomaly_id=anomaly_id, error=str(e))
        return {
            "status": "failed",
            "anomaly_id": anomaly_id,
            "error": str(e),
        }
