"""Mask Refinement Celery 任务 — 背景消除和图像标准化"""
from __future__ import annotations

from app.infrastructure.queue.celery_app import celery_app
from app.common.logging import get_logger

logger = get_logger(__name__)


@celery_app.task(name="mask.refine_single")
def refine_single_anomaly(
    anomaly_id: str,
    crop_path: str,
    *,
    use_grabcut: bool = True,
    equalize_hist: bool = True,
) -> dict:
    """对单个 anomaly 的 crop 执行 mask 精化，上传 refined 结果到 MinIO"""
    import asyncio

    async def _refine() -> dict:
        from app.infrastructure.storage.minio_client import minio_client
        from app.services.mask_refinement import MaskRefinementService

        service = MaskRefinementService()
        refined_bytes = await service.refine_from_minio(
            crop_path,
            use_grabcut=use_grabcut,
            equalize_hist=equalize_hist,
        )

        if refined_bytes is None:
            return {"status": "failed", "anomaly_id": anomaly_id, "error": "Download or refine failed"}

        # 上传 refined 图片到 MinIO
        refined_path = f"refined/{anomaly_id}_refined.png"
        try:
            await minio_client.upload(refined_path, refined_bytes, content_type="image/png")
        except Exception as exc:
            logger.error("mask_refine_upload_failed", anomaly_id=anomaly_id, error=str(exc))
            return {"status": "failed", "anomaly_id": anomaly_id, "error": str(exc)}

        # 更新 anomaly record 的 refined_path
        from app.infrastructure.database.session import async_session_factory
        from app.repositories.anomaly.repository import AnomalyRepository

        async with async_session_factory() as session:
            repo = AnomalyRepository(session)
            anomaly = await repo.get_by_id(anomaly_id)
            if anomaly is not None:
                anomaly.refined_crop_path = refined_path
                await repo.update(anomaly)

        # 双轨：从 refined crop 提取 embedding 用于对比评估
        from app.workers.embedding_worker.tasks import extract_embedding_for_anomaly
        extract_embedding_for_anomaly.delay(
            anomaly_id=anomaly_id,
            crop_path=refined_path,
            embedding_type="refined",
        )

        logger.info("mask_refine_complete", anomaly_id=anomaly_id, refined_path=refined_path)
        return {
            "status": "completed",
            "anomaly_id": anomaly_id,
            "refined_path": refined_path,
        }

    return asyncio.run(_refine())


@celery_app.task(name="mask.refine_batch")
def refine_batch(batch_size: int = 100) -> dict:
    """批量处理 pending 状态的 anomaly，执行 mask 精化"""
    import asyncio

    async def _batch_refine() -> dict:
        from app.infrastructure.database.session import async_session_factory
        from app.repositories.anomaly.repository import AnomalyRepository

        async with async_session_factory() as session:
            repo = AnomalyRepository(session)
            unprocessed = await repo.get_unprocessed(limit=batch_size)

        results = []
        for anomaly in unprocessed:
            if anomaly.crop_path is None:
                continue
            result = refine_single_anomaly.delay(
                anomaly_id=anomaly.id,
                crop_path=anomaly.crop_path,
            )
            results.append({"anomaly_id": anomaly.id, "task_id": str(result.id)})

        logger.info("mask_refine_batch_dispatched", count=len(results))
        return {"status": "dispatched", "dispatched_count": len(results), "tasks": results}

    return asyncio.run(_batch_refine())
