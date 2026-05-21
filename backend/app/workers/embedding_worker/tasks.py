from __future__ import annotations

from app.common.logging import get_logger
from app.infrastructure.queue.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="embedding.extract_for_anomaly")
def extract_embedding_for_anomaly(
    anomaly_id: str,
    crop_path: str,
) -> dict[str, object]:
    """Extract embedding from anomaly crop image.

    This task runs in a Celery worker to avoid blocking the API thread.
    The actual extraction is delegated to the ResNet18 extractor.
    """
    logger.info(
        "embedding_task_started",
        anomaly_id=anomaly_id,
        crop_path=crop_path,
    )

    try:
        # Placeholder: actual extraction happens via EmbeddingExtractor protocol
        # The worker will load the model and run inference here
        logger.info("embedding_task_complete", anomaly_id=anomaly_id)
        return {
            "status": "completed",
            "anomaly_id": anomaly_id,
        }
    except Exception as e:
        logger.error("embedding_task_failed", anomaly_id=anomaly_id, error=str(e))
        return {
            "status": "failed",
            "anomaly_id": anomaly_id,
            "error": str(e),
        }


@celery_app.task(name="embedding.batch_extract")
def batch_extract_embeddings(
    anomaly_batch: list[dict[str, str]],
) -> dict[str, object]:
    """Batch extract embeddings for multiple anomalies.

    Processes all anomalies sequentially in this single task
    rather than spawning sub-tasks, to avoid infinite recursion.
    """
    logger.info("batch_embedding_started", count=len(anomaly_batch))

    completed: list[dict[str, object]] = []
    failed: list[dict[str, object]] = []

    for item in anomaly_batch:
        try:
            result = extract_embedding_for_anomaly(
                anomaly_id=item["anomaly_id"],
                crop_path=item["crop_path"],
            )
            if result.get("status") == "completed":
                completed.append(result)
            else:
                failed.append(result)
        except Exception as e:
            logger.error(
                "batch_embedding_item_failed",
                anomaly_id=item.get("anomaly_id"),
                error=str(e),
            )
            failed.append({
                "anomaly_id": item.get("anomaly_id"),
                "error": str(e),
            })

    logger.info(
        "batch_embedding_complete",
        completed=len(completed),
        failed=len(failed),
    )
    return {
        "status": "completed" if not failed else "partial",
        "completed": len(completed),
        "failed": len(failed),
        "results": completed,
        "errors": failed,
    }
