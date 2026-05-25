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
        """HDBSCAN 在原始嵌入空间聚类，UMAP 仅用于 2D 可视化坐标。

        HDBSCAN 在小数据集/稀疏数据上可能把高相似度点对判为 noise（缺乏密度对比）。
        此时 fallback 到余弦相似度连通分量法，确保 identical/similar 嵌入能成簇。

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

        # HDBSCAN 在原始高维空间聚类
        self._hdbscan = HDBSCAN(
            min_cluster_size=min(self._hdbscan_min_cluster_size, len(scaled) - 1),
            min_samples=min(self._hdbscan_min_samples, len(scaled) - 1),
            metric=self._hdbscan_metric,
        )
        labels = self._hdbscan.fit_predict(scaled)
        probabilities = self._hdbscan.probabilities_

        # Fallback: 当 HDBSCAN 把全部点判为 noise 时，用余弦相似度连通分量法
        if np.all(labels == -1):
            labels, probabilities = self._cosine_similarity_clustering(
                scaled, self._hdbscan_min_cluster_size
            )

        # UMAP 仅用于 2D 可视化；小数据集可能触发 k>=N 错误，回退到 PCA
        try:
            self._umap = UMAP(
                n_components=self._umap_n_components,
                n_neighbors=min(self._umap_n_neighbors, len(scaled) - 1),
                min_dist=self._umap_min_dist,
                random_state=self._random_state,
            )
            umap_result = self._umap.fit_transform(scaled)
        except (ValueError, TypeError):
            from sklearn.decomposition import PCA
            pca = PCA(n_components=min(2, scaled.shape[1]))
            umap_result = pca.fit_transform(scaled)

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

    @staticmethod
    def _cosine_similarity_clustering(
        embeddings: np.ndarray,
        min_cluster_size: int,
        *,
        threshold: float = 0.95,
    ) -> tuple[np.ndarray, np.ndarray]:
        """余弦相似度连通分量聚类 — HDBSCAN 对小/稀疏数据集的 fallback。

        构建相似度图：余弦相似度 > threshold 的点之间连边，
        然后找出所有连通分量，分量大小 >= min_cluster_size 的成为 cluster。
        """
        from sklearn.metrics.pairwise import cosine_similarity

        n = len(embeddings)
        sim_matrix = cosine_similarity(embeddings)
        labels = np.full(n, -1, dtype=int)
        probabilities = np.zeros(n, dtype=float)

        # BFS 找连通分量
        visited = np.zeros(n, dtype=bool)
        adjacency = sim_matrix > threshold

        cluster_id = 0
        for start in range(n):
            if visited[start]:
                continue
            # BFS
            queue = [start]
            visited[start] = True
            component: list[int] = []
            while queue:
                node = queue.pop(0)
                component.append(node)
                for neighbor in range(n):
                    if adjacency[node, neighbor] and not visited[neighbor]:
                        visited[neighbor] = True
                        queue.append(neighbor)

            if len(component) >= min_cluster_size:
                for idx in component:
                    labels[idx] = cluster_id
                    # 用分量内平均相似度作为 confidence
                    comp_sims = [sim_matrix[idx, other] for other in component if other != idx]
                    probabilities[idx] = float(np.mean(comp_sims)) if comp_sims else 1.0
                cluster_id += 1

        return labels, probabilities

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
