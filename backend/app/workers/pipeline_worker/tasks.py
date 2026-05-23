from __future__ import annotations

from celery import chain

from app.common.logging import get_logger
from app.infrastructure.database.session import async_session_factory
from app.infrastructure.queue.celery_app import celery_app
from app.repositories.anomaly.repository import AnomalyRepository
from app.repositories.cluster.repository import ClusterRepository
from app.workers import run_async

logger = get_logger(__name__)


@celery_app.task(name="pipeline.process_new_anomalies")
def process_new_anomalies(limit: int = 500) -> dict[str, object]:
    """Orchestrate the full pipeline for all pending anomalies.

    Flow: pending anomalies → batch embed → clustering → VLM analysis per cluster
    """
    logger.info("pipeline_process_started", limit=limit)

    async def _run() -> dict[str, object]:
        async with async_session_factory() as session:
            anomaly_repo = AnomalyRepository(session)
            pending = await anomaly_repo.get_unprocessed(limit=limit)

        if not pending:
            logger.info("pipeline_no_pending_anomalies")
            return {"status": "skipped", "reason": "no_pending"}

        batch = [
            {"anomaly_id": a.id, "crop_path": a.crop_path or ""}
            for a in pending
            if a.crop_path
        ]

        if not batch:
            logger.info("pipeline_no_crops")
            return {"status": "skipped", "reason": "no_crop_paths"}

        pipeline = chain(
            celery_app.signature(
                "embedding.batch_extract",
                kwargs={"anomaly_batch": batch},
            ),
            celery_app.signature(
                "clustering.run",
                kwargs={},
            ).si(),  # immutable: 丢弃前一步结果，只用 kwargs
            celery_app.signature("pipeline.trigger_vlm_on_new_clusters"),
        )
        result = pipeline.delay()

        logger.info("pipeline_dispatched", task_id=result.id, anomaly_count=len(batch))
        return {"status": "dispatched", "task_id": result.id, "anomaly_count": len(batch)}

    return run_async(_run())


@celery_app.task(name="pipeline.trigger_vlm_on_new_clusters")
def trigger_vlm_on_new_clusters(
    previous_result: dict[str, object] | None = None,
) -> dict[str, object]:
    """After clustering completes, trigger VLM analysis on newly created clusters."""
    logger.info("vlm_trigger_check", previous_result=previous_result)

    async def _run() -> dict[str, object]:
        async with async_session_factory() as session:
            cluster_repo = ClusterRepository(session)
            pending_review = await cluster_repo.get_by_status("pending_review", offset=0, limit=50)

        if not pending_review:
            logger.info("vlm_no_clusters_for_review")
            return {"status": "skipped", "reason": "no_pending_review"}

        import json

        tasks = []
        for cluster in pending_review:
            rep_paths = json.loads(cluster.representative_ids or "[]")
            if rep_paths:
                tasks.append({
                    "cluster_id": cluster.id,
                    "paths": rep_paths,
                })

        if tasks:
            result = celery_app.signature("vlm.batch_analyze", kwargs={"clusters": tasks}).delay()
            logger.info("vlm_batch_dispatched", cluster_count=len(tasks), task_id=result.id)
            return {"status": "dispatched", "cluster_count": len(tasks), "task_id": result.id}

        return {"status": "skipped", "reason": "no_representatives"}

    return run_async(_run())


@celery_app.task(name="pipeline.full_cycle")
def run_full_cycle(limit: int = 500) -> dict[str, object]:
    """Run the complete offline analysis cycle.

    Embed → Cluster → VLM → (engineer reviews via UI) → Train → Deploy
    """
    logger.info("full_cycle_started", limit=limit)
    return process_new_anomalies(limit=limit)
