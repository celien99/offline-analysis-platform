from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.logging import get_logger
from app.core.config import settings
from app.core.exceptions import ClusteringError
from app.core.security import generate_uuid
from app.domain.clustering import ClusterConfig, ClusterResult, ClusteringResult
from app.models.cluster import Cluster, ClusterMembership
from app.repositories.anomaly.repository import AnomalyRepository
from app.repositories.cluster.repository import ClusterMembershipRepository, ClusterRepository
from app.repositories.embedding.repository import EmbeddingRepository

logger = get_logger(__name__)


class ClusteringService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._cluster_repo = ClusterRepository(session)
        self._membership_repo = ClusterMembershipRepository(session)
        self._embedding_repo = EmbeddingRepository(session)
        self._anomaly_repo = AnomalyRepository(session)

    def _build_cluster_config(self) -> ClusterConfig:
        return ClusterConfig(
            umap_n_components=settings.umap_n_components,
            umap_n_neighbors=settings.umap_n_neighbors,
            hdbscan_min_cluster_size=settings.clustering_min_cluster_size,
            hdbscan_min_samples=settings.clustering_min_samples,
        )

    async def run_clustering(
        self,
        embeddings: dict[str, np.ndarray],
        *,
        config: ClusterConfig | None = None,
    ) -> tuple[ClusteringResult, dict[str, int], dict[str, float]]:
        cfg = config or self._build_cluster_config()

        num_samples = len(embeddings)
        effective_min_cluster_size = min(cfg.hdbscan_min_cluster_size, num_samples)
        effective_min_samples = min(cfg.hdbscan_min_samples, num_samples)

        if num_samples < effective_min_cluster_size:
            raise ClusteringError(
                f"Need at least {effective_min_cluster_size} embeddings for clustering, got {num_samples}"
            )

        ids = list(embeddings.keys())
        matrix = np.stack([embeddings[i] for i in ids])

        from ml.clustering.pipeline import ClusteringPipeline

        pipeline = ClusteringPipeline(
            umap_n_components=cfg.umap_n_components,
            umap_n_neighbors=cfg.umap_n_neighbors,
            umap_min_dist=cfg.umap_min_dist,
            hdbscan_min_cluster_size=effective_min_cluster_size,
            hdbscan_min_samples=effective_min_samples,
            hdbscan_metric=cfg.hdbscan_metric,
        )

        try:
            result = pipeline.fit_predict(matrix, ids)
        except Exception as e:
            logger.error("clustering_failed", error=str(e))
            raise ClusteringError(f"Clustering failed: {e}") from e

        labels: np.ndarray = result["labels"]
        probabilities: np.ndarray = result["probabilities"]
        umap_coords: np.ndarray = result["umap_coords"]

        representatives = pipeline.get_representatives(labels, probabilities, n_per_cluster=5)

        label_map: dict[str, int] = dict(zip(ids, (int(lb) for lb in labels)))
        probability_map: dict[str, float] = dict(zip(ids, (float(p) for p in probabilities)))

        run_at = datetime.now(tz=timezone.utc)

        clusters: list[ClusterResult] = []
        unique_labels = set(labels)
        noise_count = int(sum(1 for lb in labels if lb == -1))

        for label in sorted(unique_labels):
            if label == -1:
                continue
            int_label = int(label)
            label_indices = [i for i, lb in enumerate(labels) if lb == label]
            centroid = matrix[label_indices].mean(axis=0).tolist()
            umap_points = umap_coords[label_indices]
            umap_center = umap_points.mean(axis=0)

            rep_indices = representatives.get(int_label, [])
            rep_ids = [ids[i] for i in rep_indices] if rep_indices else []

            cluster = ClusterResult(
                cluster_id=generate_uuid(),
                label=int_label,
                sample_count=len(label_indices),
                representative_ids=rep_ids,
                centroid=centroid,
                umap_x=float(umap_center[0]),
                umap_y=float(umap_center[1]),
                probability=float(probabilities[label_indices].mean()),
            )
            clusters.append(cluster)

        logger.info(
            "clustering_complete",
            num_clusters=len(clusters),
            noise_count=noise_count,
            total_samples=len(ids),
        )

        result = ClusteringResult(
            clusters=clusters,
            noise_count=noise_count,
            total_samples=len(ids),
            parameters=cfg,
            run_at=run_at,
        )
        return result, label_map, probability_map

    async def persist_clustering_result(
        self,
        result: ClusteringResult,
        *,
        label_map: dict[str, int] | None = None,
        probability_map: dict[str, float] | None = None,
        seat_model_id: str | None = None,
        camera_id: str | None = None,
    ) -> list[Cluster]:
        persisted: list[Cluster] = []
        for cr in result.clusters:
            cluster = Cluster(
                id=cr.cluster_id,
                seat_model_id=seat_model_id,
                camera_id=camera_id,
                hdbscan_label=cr.label,
                sample_count=cr.sample_count,
                representative_ids=json.dumps(cr.representative_ids),
                centroid=json.dumps(cr.centroid) if cr.centroid else None,
                umap_x=cr.umap_x,
                umap_y=cr.umap_y,
                hdbscan_probability=cr.probability,
                possible_type=cr.possible_type,
                status="pending_review",
                clustering_run_at=result.run_at,
            )
            persisted.append(await self._cluster_repo.create(cluster))

            if label_map is not None:
                memberships = [
                    ClusterMembership(
                        id=generate_uuid(),
                        cluster_id=cr.cluster_id,
                        anomaly_id=aid,
                        membership_score=probability_map.get(aid, cr.probability)
                        if probability_map
                        else cr.probability,
                    )
                    for aid, lbl in label_map.items()
                    if lbl == cr.label
                ]
            else:
                memberships = [
                    ClusterMembership(
                        id=generate_uuid(),
                        cluster_id=cr.cluster_id,
                        anomaly_id=aid,
                        membership_score=cr.probability,
                    )
                    for aid in cr.representative_ids
                ]
            await self._membership_repo.bulk_create(memberships)

        return persisted

    async def get_cluster_detail(self, cluster_id: str) -> Cluster | None:
        return await self._cluster_repo.get_by_id(cluster_id)

    async def list_clusters(
        self,
        *,
        status: str | None = None,
        review_status: str | None = None,
        defect_type: str | None = None,
        seat_model_id: str | None = None,
        camera_id: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Cluster], int]:
        clusters = await self._cluster_repo.list_all(
            status=status,
            review_status=review_status,
            defect_type=defect_type,
            seat_model_id=seat_model_id,
            camera_id=camera_id,
            offset=offset,
            limit=limit,
        )
        total = await self._cluster_repo.count(
            status=status,
            review_status=review_status,
            defect_type=defect_type,
            seat_model_id=seat_model_id,
            camera_id=camera_id,
        )
        return list(clusters), total

    async def get_cluster_anomaly_ids(self, cluster_id: str) -> list[str]:
        return await self._membership_repo.get_anomaly_ids_by_cluster(cluster_id)
