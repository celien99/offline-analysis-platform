"""双轨对比服务：比较 raw vs refined embedding 的聚类质量。

评估维度：
  - 簇数量（更多不一定更好，需要在纯度和粒度之间平衡）
  - 噪声率（HDBSCAN label=-1 的比例，越低越好）
  - 平均簇大小和标准差（簇大小分布应均匀）
  - 最大簇占比（避免一个大簇吞掉所有样本）
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np

from app.common.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TrackMetrics:
    """单条轨道（raw 或 refined）的聚类质量指标。"""
    embedding_type: str
    sample_count: int
    cluster_count: int
    noise_count: int
    noise_rate: float
    avg_cluster_size: float
    max_cluster_size: int
    max_cluster_ratio: float  # 最大簇占总样本的比例
    cluster_sizes: list[int]


@dataclass
class ComparisonReport:
    """双轨对比报告。"""
    seat_model_id: str | None
    camera_id: str | None
    raw_metrics: TrackMetrics | None
    refined_metrics: TrackMetrics | None
    recommendation: str
    evaluated_at: datetime

    def to_dict(self) -> dict[str, object]:
        def _track_dict(tm: TrackMetrics | None) -> dict[str, object] | None:
            if tm is None:
                return None
            return {
                "embedding_type": tm.embedding_type,
                "sample_count": tm.sample_count,
                "cluster_count": tm.cluster_count,
                "noise_count": tm.noise_count,
                "noise_rate": round(tm.noise_rate, 4),
                "avg_cluster_size": round(tm.avg_cluster_size, 1),
                "max_cluster_size": tm.max_cluster_size,
                "max_cluster_ratio": round(tm.max_cluster_ratio, 4),
                "cluster_sizes": tm.cluster_sizes,
            }
        return {
            "seat_model_id": self.seat_model_id,
            "camera_id": self.camera_id,
            "raw": _track_dict(self.raw_metrics),
            "refined": _track_dict(self.refined_metrics),
            "recommendation": self.recommendation,
            "evaluated_at": self.evaluated_at.isoformat(),
        }


class DualTrackComparison:
    """双轨对比引擎。

    在相同 anomaly 集合上分别用 raw 和 refined embedding 执行聚类，
    比较聚类质量指标，给出推荐。
    """

    async def compare(
        self,
        seat_model_id: str | None = None,
        camera_id: str | None = None,
    ) -> ComparisonReport:
        """执行双轨对比并返回报告。"""
        from app.infrastructure.database.session import async_session_factory
        from app.repositories.embedding.repository import EmbeddingRepository

        async with async_session_factory() as session:
            repo = EmbeddingRepository(session)

            # 获取 raw 和 refined embedding
            raw_rows = await repo.get_embeddings_for_clustering(
                seat_model_id=seat_model_id,
                camera_id=camera_id,
                embedding_type="raw",
            )
            refined_rows = await repo.get_embeddings_for_clustering(
                seat_model_id=seat_model_id,
                camera_id=camera_id,
                embedding_type="refined",
            )

        raw_metrics = await self._evaluate_track(raw_rows, "raw")
        refined_metrics = await self._evaluate_track(refined_rows, "refined")

        recommendation = self._make_recommendation(raw_metrics, refined_metrics)

        return ComparisonReport(
            seat_model_id=seat_model_id,
            camera_id=camera_id,
            raw_metrics=raw_metrics,
            refined_metrics=refined_metrics,
            recommendation=recommendation,
            evaluated_at=datetime.now(tz=timezone.utc),
        )

    async def _evaluate_track(
        self,
        rows: list[tuple[str, list[float]]],
        embedding_type: str,
    ) -> TrackMetrics | None:
        """对单轨 embedding 执行聚类并收集指标。"""
        if len(rows) < 5:
            logger.info("comparison_insufficient_samples", embedding_type=embedding_type, count=len(rows))
            return None

        ids = [r[0] for r in rows]
        matrix = np.stack([r[1] for r in rows], dtype=np.float32)

        from ml.clustering.pipeline import ClusteringPipeline
        from app.core.config import settings

        pipeline = ClusteringPipeline(
            umap_n_components=settings.umap_n_components,
            umap_n_neighbors=min(settings.umap_n_neighbors, len(rows) - 1),
            umap_min_dist=0.1,
            hdbscan_min_cluster_size=min(settings.clustering_min_cluster_size, len(rows)),
            hdbscan_min_samples=min(settings.clustering_min_samples, len(rows)),
            hdbscan_metric="euclidean",
        )

        try:
            result = pipeline.fit_predict(matrix, ids)
        except Exception as e:
            logger.error("comparison_clustering_failed", embedding_type=embedding_type, error=str(e))
            return None

        labels = result["labels"]
        noise_count = int(sum(1 for lb in labels if lb == -1))
        unique_labels = [int(lb) for lb in set(labels) if lb != -1]

        cluster_sizes = [
            int(sum(1 for lb in labels if lb == label))
            for label in unique_labels
        ]
        cluster_count = len(cluster_sizes)

        return TrackMetrics(
            embedding_type=embedding_type,
            sample_count=len(rows),
            cluster_count=cluster_count,
            noise_count=noise_count,
            noise_rate=noise_count / len(rows) if len(rows) > 0 else 0.0,
            avg_cluster_size=sum(cluster_sizes) / cluster_count if cluster_count > 0 else 0.0,
            max_cluster_size=max(cluster_sizes) if cluster_sizes else 0,
            max_cluster_ratio=(max(cluster_sizes) / len(rows)) if cluster_sizes and len(rows) > 0 else 0.0,
            cluster_sizes=sorted(cluster_sizes, reverse=True),
        )

    def _make_recommendation(
        self,
        raw: TrackMetrics | None,
        refined: TrackMetrics | None,
    ) -> str:
        """基于指标给出推荐建议。"""
        if raw is None and refined is None:
            return "样本不足，无法对比"
        if raw is None:
            return "raw 嵌入不足，仅有 refined 结果"
        if refined is None:
            return "refined 嵌入不足，继续使用 raw 嵌入"

        reasons: list[str] = []

        # 噪声率比较
        if refined.noise_rate < raw.noise_rate:
            reasons.append(f"refined 噪声率更低 ({refined.noise_rate:.1%} vs {raw.noise_rate:.1%})")
        elif refined.noise_rate > raw.noise_rate:
            reasons.append(f"raw 噪声率更低 ({raw.noise_rate:.1%} vs {refined.noise_rate:.1%})")

        # 簇数量：不是越多越好，而是看能否发现更多有意义的分组
        if refined.cluster_count > raw.cluster_count:
            reasons.append(f"refined 发现更多簇 ({refined.cluster_count} vs {raw.cluster_count})")
        else:
            reasons.append(f"raw 发现更多簇 ({raw.cluster_count} vs {refined.cluster_count})")

        # 最大簇占比
        if refined.max_cluster_ratio < raw.max_cluster_ratio:
            reasons.append(f"refined 最大簇更集中 ({refined.max_cluster_ratio:.1%} vs {raw.max_cluster_ratio:.1%})")

        # 综合判断
        refined_score = 0
        if refined.noise_rate < raw.noise_rate:
            refined_score += 1
        if refined.max_cluster_ratio < raw.max_cluster_ratio:
            refined_score += 1

        if refined_score >= 2:
            return f"推荐使用 refined 嵌入 — {'; '.join(reasons)}"
        elif refined_score == 1:
            return f"refined 和 raw 各有优势，建议人工复核 — {'; '.join(reasons)}"
        else:
            return f"当前建议继续使用 raw 嵌入 — {'; '.join(reasons)}"
