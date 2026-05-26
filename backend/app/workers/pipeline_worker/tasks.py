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
        from collections import defaultdict

        async with async_session_factory() as session:
            anomaly_repo = AnomalyRepository(session)
            pending = await anomaly_repo.get_unprocessed(limit=limit)

        if not pending:
            logger.info("pipeline_no_pending_anomalies")
            return {"status": "skipped", "reason": "no_pending"}

        # 按 seat_model_id + camera_id + region_id 三级隔离分组
        # 分组键格式: "model::camera::region"，None 用 __unknown__ 占位
        def _build_group_key(a: object) -> str:
            sm = a.seat_model_id or "__unknown__"
            cam = a.camera_id or "__unknown__"
            reg = a.region_id or "__unknown__"
            return f"{sm}::{cam}::{reg}"

        groups: dict[str, dict[str, object]] = defaultdict(lambda: {
            "anomalies": [],
            "seat_model_id": None,
            "camera_id": None,
            "region_id": None,
        })
        for a in pending:
            if a.crop_path:
                key = _build_group_key(a)
                groups[key]["anomalies"].append({
                    "anomaly_id": a.id,
                    "crop_path": a.crop_path,
                })
                if a.seat_model_id:
                    groups[key]["seat_model_id"] = a.seat_model_id
                if a.camera_id:
                    groups[key]["camera_id"] = a.camera_id
                if a.region_id:
                    groups[key]["region_id"] = a.region_id

        if not groups:
            logger.info("pipeline_no_crops")
            return {"status": "skipped", "reason": "no_crop_path"}

        # 解析分组键，按 seat_model_id 聚合 celery chain
        # 同一个 seat_model_id 下可能有多个 camera/region 分组
        from collections import defaultdict as dd
        sm_groups: dict[str, list[dict[str, object]]] = dd(list)
        for key, group_data in groups.items():
            sm = group_data["seat_model_id"] or "__unknown__"
            sm_groups[sm].append({
                "key": key,
                "batch": group_data["anomalies"],
                "camera_id": group_data["camera_id"],
                "region_id": group_data["region_id"],
            })

        task_ids: list[str] = []
        for sm_id, sub_batches in sm_groups.items():
            for sub in sub_batches:
                if not sub["batch"]:
                    continue
                pipeline = chain(
                    celery_app.signature(
                        "embedding.batch_extract",
                        kwargs={"anomaly_batch": sub["batch"]},
                    ),
                    celery_app.signature(
                        "clustering.run",
                        kwargs={
                            "seat_model_id": sm_id if sm_id != "__unknown__" else None,
                            "camera_id": sub["camera_id"],
                            "region_id": sub["region_id"],
                        },
                        immutable=True,
                    ),
                    celery_app.signature("pipeline.trigger_vlm_on_new_clusters"),
                )
                result = pipeline.delay()
                task_ids.append(result.id)
                logger.info(
                    "pipeline_dispatched",
                    task_id=result.id,
                    seat_model_id=sm_id,
                    camera_id=sub["camera_id"],
                    region_id=sub["region_id"],
                    anomaly_count=len(sub["batch"]),
                )

        return {
            "status": "dispatched",
            "task_ids": task_ids,
            "anomaly_count": sum(
                len(sub["batch"]) for subs in sm_groups.values() for sub in subs
            ),
            "groups": len(task_ids),
        }

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
    """Run the offline analysis pipeline: Embed → Cluster → VLM.

    Engineer review, training and deployment are triggered separately via UI.
    """
    logger.info("full_cycle_started", limit=limit)
    return process_new_anomalies(limit=limit)
