from __future__ import annotations

import numpy as np
from hdbscan import HDBSCAN
from sklearn.preprocessing import StandardScaler
from umap import UMAP


class ClusteringPipeline:
    """UMAP + HDBSCAN clustering pipeline for anomaly embeddings.

    Reduces high-dimensional embedding vectors to 2D via UMAP,
    then clusters with HDBSCAN to discover anomaly patterns.
    """

    def __init__(
        self,
        umap_n_components: int = 2,
        umap_n_neighbors: int = 15,
        umap_min_dist: float = 0.1,
        hdbscan_min_cluster_size: int = 10,
        hdbscan_min_samples: int = 5,
        hdbscan_metric: str = "euclidean",
        random_state: int = 42,
    ) -> None:
        self._umap_n_components = umap_n_components
        self._umap_n_neighbors = umap_n_neighbors
        self._umap_min_dist = umap_min_dist
        self._hdbscan_min_cluster_size = hdbscan_min_cluster_size
        self._hdbscan_min_samples = hdbscan_min_samples
        self._hdbscan_metric = hdbscan_metric
        self._random_state = random_state

        self._umap: UMAP | None = None
        self._hdbscan: HDBSCAN | None = None
        self._scaler: StandardScaler | None = None

    def fit_predict(
        self,
        embeddings: np.ndarray,
        ids: list[str],
    ) -> dict[str, object]:
        """Fit UMAP + HDBSCAN on embeddings and return cluster assignments.

        Args:
            embeddings: (n_samples, n_features) numpy array
            ids: List of sample IDs in same order as embeddings

        Returns:
            dict with keys: labels, probabilities, umap_coords, cluster_groups
        """
        if len(embeddings) < self._hdbscan_min_cluster_size:
            return {
                "labels": np.full(len(embeddings), -1),
                "probabilities": np.zeros(len(embeddings)),
                "umap_coords": np.zeros((len(embeddings), 2)),
                "cluster_groups": {},
            }

        self._scaler = StandardScaler()
        scaled = self._scaler.fit_transform(embeddings)

        self._umap = UMAP(
            n_components=self._umap_n_components,
            n_neighbors=min(self._umap_n_neighbors, len(scaled) - 1),
            min_dist=self._umap_min_dist,
            random_state=self._random_state,
        )
        umap_result = self._umap.fit_transform(scaled)

        self._hdbscan = HDBSCAN(
            min_cluster_size=min(self._hdbscan_min_cluster_size, len(scaled) - 1),
            min_samples=min(self._hdbscan_min_samples, len(scaled) - 1),
            metric=self._hdbscan_metric,
        )
        labels = self._hdbscan.fit_predict(umap_result)
        probabilities = self._hdbscan.probabilities_

        cluster_groups: dict[int, list[str]] = {}
        for i, (label, sample_id) in enumerate(zip(labels, ids)):
            label_int = int(label)
            if label_int not in cluster_groups:
                cluster_groups[label_int] = []
            cluster_groups[label_int].append(sample_id)

        return {
            "labels": labels,
            "probabilities": probabilities,
            "umap_coords": umap_result,
            "cluster_groups": cluster_groups,
        }

    def get_representatives(
        self,
        labels: np.ndarray,
        probabilities: np.ndarray,
        n_per_cluster: int = 5,
    ) -> dict[int, list[int]]:
        """Get the top-N representative samples per cluster by probability."""
        representatives: dict[int, list[int]] = {}
        unique_labels = set(labels)
        for label in unique_labels:
            if label == -1:
                continue
            indices = np.where(labels == label)[0]
            sorted_indices = indices[np.argsort(probabilities[indices])[::-1]]
            representatives[int(label)] = sorted_indices[:n_per_cluster].tolist()
        return representatives
