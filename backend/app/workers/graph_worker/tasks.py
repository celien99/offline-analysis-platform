"""相似度图谱构建 Celery 任务"""
from __future__ import annotations

from app.infrastructure.queue.celery_app import celery_app
from app.common.logging import get_logger

logger = get_logger(__name__)


@celery_app.task(name="graph.build", bind=True, max_retries=3)
def build_similarity_graph(self, k: int = 10) -> dict:
    """异步构建相似度图谱"""
    import asyncio
    from app.infrastructure.database.session import async_session_factory
    from app.services.graph import GraphService

    async def _build() -> dict:
        async with async_session_factory() as session:
            service = GraphService(session)
            record = await service.build_graph(k=k)
            return {
                "build_id": record.id,
                "status": record.status,
                "total_anomalies": record.total_anomalies,
                "total_edges": record.total_edges,
            }

    try:
        result = asyncio.run(_build())
        logger.info("graph_build_task_complete", **result)
        return result
    except Exception as exc:
        logger.error("graph_build_task_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="graph.schedule_rebuild")
def schedule_graph_rebuild(k: int = 10) -> dict:
    """定时重建图谱 — 由 Celery Beat 调度"""
    return build_similarity_graph.delay(k=k).get()
