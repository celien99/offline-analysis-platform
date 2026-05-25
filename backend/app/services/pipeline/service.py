"""Pipeline 编排服务 — 将 embedding / clustering / VLM 步骤编排为 Celery chain。

所有 CPU/GPU 密集型任务通过 Celery worker 异步执行，
不在 FastAPI 请求进程内阻塞。
"""

from __future__ import annotations

from app.common.logging import get_logger

logger = get_logger(__name__)


class PipelineService:
    """离线分析流水线编排器。

    Flow: pending anomalies → batch_embed → clustering → VLM per cluster

    所有步骤由 Celery chain 异步执行，调用方 fire-and-forget 即可。
    """

    def dispatch_for_new_anomalies(self, limit: int = 500) -> str | None:
        """扫描所有 status=pending 的异常，触发完整的 embedding→聚类→VLM 流水线。

        Returns:
            Celery chain task_id，如果无待处理异常则返回 None
        """
        from app.workers.pipeline_worker.tasks import process_new_anomalies

        result = process_new_anomalies.delay(limit=limit)
        logger.info("pipeline_dispatched", task_id=result.id, limit=limit)
        return result.id

    def dispatch_embedding_only(self, anomaly_batch: list[dict[str, str]]) -> str:
        """仅触发 embedding 提取（不接聚类），用于单条补提场景。

        Args:
            anomaly_batch: [{"anomaly_id": ..., "crop_path": ...}, ...]
        """
        from app.infrastructure.queue.celery_app import celery_app

        result = celery_app.signature(
            "embedding.batch_extract",
            kwargs={"anomaly_batch": anomaly_batch},
        ).delay()
        logger.info("embedding_batch_dispatched", task_id=result.id, count=len(anomaly_batch))
        return result.id

    def dispatch_single_reprocess(self, anomaly_id: str, crop_path: str) -> str:
        """单条 anomaly 重处理：仅对该 anomaly 提取 embedding，再对所有非 reviewed 做聚类。

        与 dispatch_for_new_anomalies 不同，此方法不会拉入其他 pending 异常，
        避免单条重处理触发全量扫描。
        """
        from celery import chain

        from app.infrastructure.queue.celery_app import celery_app

        pipeline = chain(
            celery_app.signature(
                "embedding.batch_extract",
                kwargs={"anomaly_batch": [{"anomaly_id": anomaly_id, "crop_path": crop_path}]},
            ),
            celery_app.signature("clustering.run", kwargs={}, immutable=True),
            celery_app.signature("pipeline.trigger_vlm_on_new_clusters"),
        )
        result = pipeline.delay()
        logger.info(
            "single_reprocess_dispatched",
            task_id=result.id,
            anomaly_id=anomaly_id,
        )
        return result.id

    def dispatch_full_chain(
        self,
        anomaly_batch: list[dict[str, str]],
    ) -> str:
        """显式编排完整链：embedding → clustering → VLM。

        与 dispatch_for_new_anomalies 不同，此方法接收明确的异常列表，
        不查询数据库。
        """
        from celery import chain

        from app.infrastructure.queue.celery_app import celery_app

        pipeline = chain(
            celery_app.signature(
                "embedding.batch_extract",
                kwargs={"anomaly_batch": anomaly_batch},
            ),
            celery_app.signature("clustering.run", kwargs={}, immutable=True),
            celery_app.signature("pipeline.trigger_vlm_on_new_clusters"),
        )
        result = pipeline.delay()
        logger.info(
            "pipeline_chain_dispatched",
            task_id=result.id,
            anomaly_count=len(anomaly_batch),
        )
        return result.id
