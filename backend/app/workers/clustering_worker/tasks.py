from __future__ import annotations

import numpy as np

from app.common.logging import get_logger
from app.core.config import settings
from app.domain.clustering import ClusterConfig
from app.infrastructure.database.session import async_session_factory
from app.infrastructure.queue.celery_app import celery_app
from app.repositories.embedding.repository import EmbeddingRepository
from app.services.clustering.service import ClusteringService
from app.workers import run_async

logger = get_logger(__name__)


def _build_cluster_config(
    min_cluster_size: int | None = None,
    min_samples: int | None = None,
) -> ClusterConfig:
    return ClusterConfig(
        umap_n_components=settings.umap_n_components,
        umap_n_neighbors=settings.umap_n_neighbors,
        umap_min_dist=0.1,
        hdbscan_min_cluster_size=min_cluster_size
        if min_cluster_size is not None
        else settings.clustering_min_cluster_size,
        hdbscan_min_samples=(
            min_samples
            if min_samples is not None
            else settings.clustering_min_samples
        ),
    )


async def _run_clustering(
    min_cluster_size: int | None = None,
    min_samples: int | None = None,
    anomaly_ids: list[str] | None = None,
    seat_model_id: str | None = None,
) -> dict[str, object]:
    async with async_session_factory() as session:
        embedding_repo = EmbeddingRepository(session)
        # 只聚类 embedded（新嵌入）和 noise（未成簇）的 anomaly，避免将已聚类的 anomaly 重新打散
        # 按 seat_model_id 分区聚类，不同座椅型号的异常不混合
        rows = await embedding_repo.get_embeddings_for_clustering(seat_model_id=seat_model_id)

    if anomaly_ids:
        rows = [(aid, vec) for aid, vec in rows if aid in anomaly_ids]

    effective_min_size = min_cluster_size if min_cluster_size is not None else settings.clustering_min_cluster_size
    if len(rows) < effective_min_size:
        logger.info("clustering_skipped_too_few", count=len(rows))
        return {"status": "skipped", "reason": "too_few_embeddings", "count": len(rows)}

    embeddings: dict[str, np.ndarray] = {
        aid: np.array(vec, dtype=np.float32) for aid, vec in rows
    }

    async with async_session_factory() as session:
        from app.repositories.cluster.repository import ClusterMembershipRepository

        # 清理本次参与聚类的 anomaly 的旧 membership，避免孤儿数据
        membership_repo = ClusterMembershipRepository(session)
        affected_ids = list(embeddings.keys())
        for aid in affected_ids:
            await membership_repo.soft_delete_by_anomaly_id(aid)

        service = ClusteringService(session)
        config = _build_cluster_config(min_cluster_size, min_samples)
        result, label_map, probability_map = await service.run_clustering(
            embeddings,
            config=config,
        )
        persisted = await service.persist_clustering_result(
            result,
            label_map=label_map,
            probability_map=probability_map,
            seat_model_id=seat_model_id,
        )

        from app.repositories.anomaly.repository import AnomalyRepository
        anomaly_repo = AnomalyRepository(session)
        for aid, label in label_map.items():
            if label >= 0:
                await anomaly_repo.update_status(aid, "clustered")
            else:
                await anomaly_repo.update_status(aid, "noise")

        await session.commit()

    logger.info(
        "clustering_task_complete",
        num_clusters=len(persisted),
        noise_count=result.noise_count,
        total=result.total_samples,
    )
    return {
        "status": "completed",
        "num_clusters": len(persisted),
        "noise_count": result.noise_count,
        "total_samples": result.total_samples,
    }


@celery_app.task(name="clustering.run")
def run_clustering(
    *,
    min_cluster_size: int | None = None,
    min_samples: int | None = None,
    anomaly_ids: list[str] | None = None,
    seat_model_id: str | None = None,
) -> dict[str, object]:
    logger.info(
        "clustering_task_started",
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        anomaly_count=len(anomaly_ids) if anomaly_ids else "all",
        seat_model_id=seat_model_id,
    )
    try:
        return run_async(_run_clustering(min_cluster_size, min_samples, anomaly_ids, seat_model_id))
    except Exception as e:
        logger.error("clustering_task_failed", error=str(e))
        return {"status": "failed", "error": str(e)}


@celery_app.task(name="clustering.schedule_regular")
def schedule_regular_clustering() -> dict[str, object]:
    logger.info("regular_clustering_scheduled")
    result = run_clustering.delay()
    return {"status": "scheduled", "task_id": result.id}
