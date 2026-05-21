from __future__ import annotations

from app.common.logging import get_logger
from app.core.config import settings
from app.domain.multimodal import VLMRequest, VLMResult
from app.infrastructure.queue.celery_app import celery_app
from app.workers import run_async

logger = get_logger(__name__)

_analyzer: object = None


def _get_analyzer():
    global _analyzer
    if _analyzer is None:
        from ml.vlm.analyzer import QwenVLMAnalyzer

        _analyzer = QwenVLMAnalyzer(
            endpoint=settings.vlm_endpoint,
            model_name=settings.vlm_model,
        )
    return _analyzer


async def _analyze_cluster(
    cluster_id: str,
    representative_paths: list[str],
) -> dict[str, object]:
    analyzer = _get_analyzer()

    request = VLMRequest(
        cluster_representative_paths=representative_paths,
        cluster_metadata={
            "cluster_id": cluster_id,
        },
    )

    try:
        result: VLMResult = await analyzer.analyze(request)
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
    representative_paths: list[str],
) -> dict[str, object]:
    logger.info(
        "vlm_analysis_started",
        cluster_id=cluster_id,
        image_count=len(representative_paths),
    )
    try:
        return run_async(_analyze_cluster(cluster_id, representative_paths))
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
        result = analyze_cluster_vlm.delay(
            cluster_id=str(c["cluster_id"]),
            representative_paths=list(c.get("paths", [])),
        )
        task_ids.append(result.id)
    logger.info("batch_vlm_dispatched", task_count=len(task_ids))
    return {"status": "dispatched", "task_ids": task_ids, "total": len(task_ids)}
