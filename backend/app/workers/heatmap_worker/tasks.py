from __future__ import annotations

from app.common.logging import get_logger
from app.infrastructure.queue.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="heatmap.generate")
def generate_heatmap(
    anomaly_id: str,
    original_path: str,
    roi_path: str | None = None,
) -> dict[str, object]:
    """Generate anomaly heatmap from original and ROI images.

    CPU-intensive task delegated to a Celery worker.
    """
    logger.info("heatmap_task_started", anomaly_id=anomaly_id)

    try:
        # Placeholder: actual heatmap generation via Grad-CAM or similar
        logger.info("heatmap_task_complete", anomaly_id=anomaly_id)
        return {
            "status": "completed",
            "anomaly_id": anomaly_id,
            "heatmap_path": None,
        }
    except Exception as e:
        logger.error("heatmap_task_failed", anomaly_id=anomaly_id, error=str(e))
        return {
            "status": "failed",
            "anomaly_id": anomaly_id,
            "error": str(e),
        }
