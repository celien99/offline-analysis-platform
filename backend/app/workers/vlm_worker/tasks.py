from __future__ import annotations

from app.common.logging import get_logger
from app.infrastructure.queue.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="vlm.analyze_cluster")
def analyze_cluster_vlm(
    cluster_id: str,
    representative_paths: list[str],
) -> dict[str, object]:
    """Analyze a cluster using VLM to generate semantic explanation.

    GPU-intensive task using Qwen2.5-VL or InternVL.
    """
    logger.info(
        "vlm_analysis_started",
        cluster_id=cluster_id,
        image_count=len(representative_paths),
    )

    try:
        # Placeholder: actual VLM analysis runs via VLMService
        logger.info("vlm_analysis_complete", cluster_id=cluster_id)
        return {
            "status": "completed",
            "cluster_id": cluster_id,
            "result": {
                "type": "unknown",
                "is_false_alarm": False,
                "reason": "Pending VLM analysis",
                "confidence": 0.0,
                "suggestion": "manual_review",
            },
        }
    except Exception as e:
        logger.error("vlm_analysis_failed", cluster_id=cluster_id, error=str(e))
        return {
            "status": "failed",
            "cluster_id": cluster_id,
            "error": str(e),
        }


@celery_app.task(name="vlm.batch_analyze")
def batch_analyze_vlm(
    clusters: list[dict[str, object]],
) -> dict[str, object]:
    """Batch VLM analysis for multiple clusters."""
    logger.info("batch_vlm_started", cluster_count=len(clusters))

    task_ids = []
    for c in clusters:
        result = analyze_cluster_vlm.delay(
            cluster_id=str(c["cluster_id"]),
            representative_paths=list(c.get("paths", [])),
        )
        task_ids.append(result.id)

    logger.info("batch_vlm_dispatched", task_count=len(task_ids))
    return {
        "status": "dispatched",
        "task_ids": task_ids,
        "total": len(task_ids),
    }
