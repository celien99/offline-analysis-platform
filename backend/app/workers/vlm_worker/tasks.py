from __future__ import annotations

from app.api.deps import get_vlm_analyzer
from app.common.logging import get_logger
from app.infrastructure.database.session import async_session_factory
from app.infrastructure.queue.celery_app import celery_app
from app.services.multimodal.service import VLMService
from app.workers import run_async

logger = get_logger(__name__)


async def _analyze_cluster(
    cluster_id: str,
) -> dict[str, object]:
    try:
        async with async_session_factory() as session:
            service = VLMService(session, get_vlm_analyzer())
            result = await service.analyze_cluster(cluster_id)
        logger.info(
            "vlm_analysis_complete",
            cluster_id=cluster_id,
            anomaly_type=result.anomaly_type,
            is_false_alarm=result.is_false_alarm,
            confidence=result.confidence,
        )
        return {
            "status": "completed",
            "cluster_id": cluster_id,
            "result": {
                "type": result.anomaly_type,
                "is_false_alarm": result.is_false_alarm,
                "reason": result.reason,
                "confidence": result.confidence,
                "suggestion": result.suggestion,
            },
        }
    except Exception as e:
        logger.error("vlm_analysis_failed", cluster_id=cluster_id, error=str(e))
        return {
            "status": "failed",
            "cluster_id": cluster_id,
            "error": str(e),
        }


@celery_app.task(name="vlm.analyze_cluster")
def analyze_cluster_vlm(
    cluster_id: str,
) -> dict[str, object]:
    logger.info("vlm_analysis_started", cluster_id=cluster_id)
    try:
        return run_async(_analyze_cluster(cluster_id))
    except Exception as e:
        logger.error("vlm_task_failed", cluster_id=cluster_id, error=str(e))
        return {"status": "failed", "cluster_id": cluster_id, "error": str(e)}


@celery_app.task(name="vlm.batch_analyze")
def batch_analyze_vlm(
    clusters: list[dict[str, object]],
) -> dict[str, object]:
    logger.info("batch_vlm_started", cluster_count=len(clusters))
    task_ids = []
    for c in clusters:
        result = analyze_cluster_vlm.delay(cluster_id=str(c["cluster_id"]))
        task_ids.append(result.id)
    logger.info("batch_vlm_dispatched", task_count=len(task_ids))
    return {"status": "dispatched", "task_ids": task_ids, "total": len(task_ids)}
