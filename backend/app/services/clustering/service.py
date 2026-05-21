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

    def _pick_representatives(
        self,
        embeddings: dict[str, np.ndarray],
        labels: np.ndarray,
        probs: np.ndarray,
    ) -> dict[int, list[str]]:
        representatives: dict[int, list[str]] = {}
        for label in set(labels):
            if label == -1:
                continue
            label_indices = [i for i, l in enumerate(labels) if l == label]
            anomaly_ids_for_label = list(embeddings.keys())
            ids_sorted = sorted(
                label_indices,
                key=lambda i: probs[i],
                reverse=True,
            )
            representatives[label] = [
                anomaly_ids_for_label[i] for i in ids_sorted[:5]
            ]
        return representatives

    async def run_clustering(
        self,
        embeddings: dict[str, np.ndarray],
        *,
        config: ClusterConfig | None = None,
    ) -> tuple[ClusteringResult, dict[str, int], dict[str, float]]:
        if len(embeddings) < max((config or ClusterConfig()).hdbscan_min_cluster_size, 3):
            raise ClusteringError(
                f"Need at least {settings.clustering_min_cluster_size} embeddings for clustering"
            )

        cfg = config or self._build_cluster_config()

        try:
            from umap import UMAP

            reducer = UMAP(
                n_components=cfg.umap_n_components,
                n_neighbors=cfg.umap_n_neighbors,
                min_dist=cfg.umap_min_dist,
                random_state=42,
            )
            ids = list(embeddings.keys())
            matrix = np.stack([embeddings[i] for i in ids])
            umap_result = reducer.fit_transform(matrix)

            from hdbscan import HDBSCAN

            clusterer = HDBSCAN(
                min_cluster_size=cfg.hdbscan_min_cluster_size,
                min_samples=cfg.hdbscan_min_samples,
                metric=cfg.hdbscan_metric,
            )
            labels = clusterer.fit_predict(matrix)
            probabilities = clusterer.probabilities_

        except Exception as e:
            logger.error("clustering_failed", error=str(e))
            raise ClusteringError(f"Clustering failed: {e}") from e

        representatives = self._pick_representatives(embeddings, labels, probabilities)
        run_at = datetime.now(tz=timezone.utc)

        # Build full anomaly ID → label mapping for membership recording
        label_map: dict[str, int] = dict(zip(ids, (int(l) for l in labels)))
        probability_map: dict[str, float] = dict(zip(ids, (float(p) for p in probabilities)))

        clusters: list[ClusterResult] = []
        unique_labels = set(labels)
        noise_count = int(sum(1 for l in labels if l == -1))

        for label in sorted(unique_labels):
            if label == -1:
                continue
            label_indices = [i for i, l in enumerate(labels) if l == label]
            centroid = matrix[label_indices].mean(axis=0).tolist()
            umap_points = umap_result[label_indices]
            umap_center = umap_points.mean(axis=0)

            cluster = ClusterResult(
                cluster_id=generate_uuid(),
                label=int(label),
                sample_count=len(label_indices),
                representative_ids=representatives.get(int(label), []),
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
    ) -> list[Cluster]:
        persisted: list[Cluster] = []
        for cr in result.clusters:
            cluster = Cluster(
                id=cr.cluster_id,
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

            # Record ALL anomaly memberships, not just representatives
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
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Cluster], int]:
        clusters = await self._cluster_repo.list_all(
            status=status, offset=offset, limit=limit
        )
        total = await self._cluster_repo.count(status=status)
        return list(clusters), total

    async def get_cluster_anomaly_ids(self, cluster_id: str) -> list[str]:
        return await self._membership_repo.get_anomaly_ids_by_cluster(cluster_id)
