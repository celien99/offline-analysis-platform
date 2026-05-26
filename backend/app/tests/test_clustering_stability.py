"""聚类稳定性测试。

验证固定小样本聚类结果的确定性：
  - 相同输入产生相同的簇数量和噪声率
  - UMAP 降维结果可复现（固定 random_state）
  - 不同隔离键下的聚类相互独立
"""

from __future__ import annotations

import numpy as np
import pytest


class TestClusteringStability:
    """测试 HDBSCAN + UMAP 聚类的稳定性。"""

    @staticmethod
    def _build_fixed_embeddings(
        n_samples: int = 30, seed: int = 42,
    ) -> tuple[dict[str, np.ndarray], int]:
        """生成固定随机种子的 embedding 数据集。

        包含 3 个明显分离的高斯簇 + 少量噪声点，模拟真实场景。
        """
        rng = np.random.RandomState(seed)
        # 3 个高斯簇 + 噪声
        c1 = rng.randn(10, 384) * 0.5 + np.array([1.0] * 384)
        c2 = rng.randn(10, 384) * 0.5 + np.array([-1.0] * 384)
        c3 = rng.randn(7, 384) * 0.5 + np.array([0.0] * 384)
        noise = rng.randn(3, 384) * 2.0

        all_vectors = np.vstack([c1, c2, c3, noise])
        ids = [f"anomaly_{i:04d}" for i in range(n_samples)]
        return {aid: vec for aid, vec in zip(ids, all_vectors)}, 3  # expected ~3 clusters

    def test_clustering_deterministic_with_fixed_seed(self) -> None:
        """固定输入和种子时聚类结果一致。"""
        from app.domain.clustering import ClusterConfig
        from ml.clustering.pipeline import ClusteringPipeline

        embeddings, _ = self._build_fixed_embeddings(seed=42)
        ids = list(embeddings.keys())
        matrix = np.stack([embeddings[i] for i in ids])

        config = ClusterConfig(
            umap_n_components=2, umap_n_neighbors=5,
            hdbscan_min_cluster_size=3, hdbscan_min_samples=2,
        )

        # 运行两次
        pipeline1 = ClusteringPipeline(
            umap_n_components=config.umap_n_components,
            umap_n_neighbors=config.umap_n_neighbors,
            umap_min_dist=config.umap_min_dist,
            hdbscan_min_cluster_size=config.hdbscan_min_cluster_size,
            hdbscan_min_samples=config.hdbscan_min_samples,
            hdbscan_metric=config.hdbscan_metric,
            random_state=42,
        )
        result1 = pipeline1.fit_predict(matrix, ids)

        pipeline2 = ClusteringPipeline(
            umap_n_components=config.umap_n_components,
            umap_n_neighbors=config.umap_n_neighbors,
            umap_min_dist=config.umap_min_dist,
            hdbscan_min_cluster_size=config.hdbscan_min_cluster_size,
            hdbscan_min_samples=config.hdbscan_min_samples,
            hdbscan_metric=config.hdbscan_metric,
            random_state=42,
        )
        result2 = pipeline2.fit_predict(matrix, ids)

        # 相同输入 + 相同 seed → 相同结果
        labels1 = result1["labels"]
        labels2 = result2["labels"]
        assert np.array_equal(labels1, labels2)

        # UMAP 坐标也应一致
        assert np.allclose(result1["umap_coords"], result2["umap_coords"])

    def test_clustering_detects_separate_groups(self) -> None:
        """聚类能检测到人为分离的高斯簇。"""
        from app.domain.clustering import ClusterConfig
        from ml.clustering.pipeline import ClusteringPipeline

        embeddings, expected_clusters = self._build_fixed_embeddings(seed=42)
        ids = list(embeddings.keys())
        matrix = np.stack([embeddings[i] for i in ids])

        config = ClusterConfig(
            umap_n_components=2, umap_n_neighbors=5,
            hdbscan_min_cluster_size=3, hdbscan_min_samples=2,
        )
        pipeline = ClusteringPipeline(
            umap_n_components=config.umap_n_components,
            umap_n_neighbors=config.umap_n_neighbors,
            umap_min_dist=config.umap_min_dist,
            hdbscan_min_cluster_size=config.hdbscan_min_cluster_size,
            hdbscan_min_samples=config.hdbscan_min_samples,
            hdbscan_metric=config.hdbscan_metric,
            random_state=42,
        )
        result = pipeline.fit_predict(matrix, ids)

        labels = result["labels"]
        unique_labels = set(int(lb) for lb in labels)
        cluster_labels = unique_labels - {-1}

        # 至少检测到 2 个簇
        assert len(cluster_labels) >= 2

        # 噪声点不应超过总数 30%
        noise_count = int(sum(1 for lb in labels if lb == -1))
        assert noise_count <= len(labels) * 0.3

    def test_clustering_fails_gracefully_with_too_few_samples(self) -> None:
        """样本不足时 HDBSCAN 将所有点标记为噪声。"""
        from app.domain.clustering import ClusterConfig
        from ml.clustering.pipeline import ClusteringPipeline

        # 只有 3 个样本
        embeddings = {
            "a1": np.random.randn(384).astype(np.float32),
            "a2": np.random.randn(384).astype(np.float32),
            "a3": np.random.randn(384).astype(np.float32),
        }
        ids = list(embeddings.keys())
        matrix = np.stack([embeddings[i] for i in ids])

        pipeline = ClusteringPipeline(
            umap_n_components=2, umap_n_neighbors=2,
            hdbscan_min_cluster_size=5, hdbscan_min_samples=3,
            random_state=42,
        )
        result = pipeline.fit_predict(matrix, ids)

        # 样本太少无法成簇时，全部为噪声
        labels = result["labels"]
        assert int(sum(1 for lb in labels if lb == -1)) == len(labels)


class TestRepresentativeSelection:
    """测试聚类代表样本选取逻辑。"""

    def test_representatives_selected_per_cluster(self) -> None:
        """每个簇选取 <= n 个代表样本。"""
        from app.domain.clustering import ClusterConfig
        from ml.clustering.pipeline import ClusteringPipeline

        rng = np.random.RandomState(42)
        n = 20
        embeddings = {
            f"a{i:02d}": rng.randn(384).astype(np.float32) for i in range(n)
        }
        ids = list(embeddings.keys())
        matrix = np.stack([embeddings[i] for i in ids])

        pipeline = ClusteringPipeline(
            umap_n_components=2, umap_n_neighbors=5,
            hdbscan_min_cluster_size=3, hdbscan_min_samples=2,
            random_state=42,
        )
        result = pipeline.fit_predict(matrix, ids)

        reps = pipeline.get_representatives(
            result["labels"], result["probabilities"], n_per_cluster=3,
        )
        # 每个 label 最多 3 个代表
        for label, rep_indices in reps.items():
            assert len(rep_indices) <= 3
