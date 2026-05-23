from __future__ import annotations

import json
from datetime import datetime, timezone
from io import BytesIO

import numpy as np
from PIL import Image

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.logging import get_logger
from app.core.exceptions import NotFoundError, VLMAnalysisError
from app.domain.multimodal import VLMAnalyzer, VLMRequest, VLMResult
from app.infrastructure.storage.minio_client import MinIOClient
from app.models.cluster import Cluster
from app.repositories.anomaly.repository import AnomalyRepository
from app.repositories.cluster.repository import ClusterMembershipRepository, ClusterRepository

logger = get_logger(__name__)


class VLMService:
    def __init__(
        self,
        session: AsyncSession,
        analyzer: VLMAnalyzer,
        minio: MinIOClient,
    ) -> None:
        self._session = session
        self._analyzer = analyzer
        self._minio = minio
        self._cluster_repo = ClusterRepository(session)
        self._membership_repo = ClusterMembershipRepository(session)
        self._anomaly_repo = AnomalyRepository(session)

    async def _download_as_ndarray(self, minio_path: str) -> np.ndarray | None:
        """从 MinIO 下载图片并转为 RGB numpy 数组。"""
        try:
            raw = await self._minio.download(minio_path)
            return np.array(Image.open(BytesIO(raw)).convert("RGB"))
        except Exception as e:
            logger.warning("vlm_download_failed", path=minio_path, error=str(e))
            return None

    async def analyze_cluster(self, cluster_id: str) -> VLMResult:
        cluster = await self._cluster_repo.get_by_id(cluster_id)
        if cluster is None:
            raise NotFoundError("Cluster", cluster_id)

        representative_ids = json.loads(cluster.representative_ids or "[]")
        anomaly_ids = representative_ids or await self._membership_repo.get_anomaly_ids_by_cluster(cluster_id)
        anomalies = await self._anomaly_repo.get_by_ids(anomaly_ids)

        # 下载缺陷裁剪图传给 VLM。
        # 只用 crop_path 和 roi_path（缺陷区域），不用 heatmap（叠加图会遮挡纹理）。
        # 从 cluster 中取最多 3 个 representative anomaly 的缺陷图。
        crop_images: list[np.ndarray] = []
        for anomaly in anomalies[:3]:  # 最多 3 个 anomaly，减少 token 消耗
            for path in [anomaly.crop_path, anomaly.roi_path]:
                if path:
                    arr = await self._download_as_ndarray(path)
                    if arr is not None:
                        crop_images.append(arr)
                        break

        if not crop_images:
            raise VLMAnalysisError(
                f"Cluster {cluster_id} 没有可用的缺陷裁剪图"
            )

        request = VLMRequest(
            crop_image=crop_images[0],                               # 主图：缺陷裁剪
            original_image=crop_images[1] if len(crop_images) > 1 else None,  # 辅图
            heatmap_image=crop_images[2] if len(crop_images) > 2 else None,   # VLMRequest 第三张图字段
            cluster_representative_paths=[],
            cluster_metadata={
                "cluster_id": cluster_id,
                "sample_count": cluster.sample_count,
                "possible_type": cluster.possible_type or "",
            },
        )

        try:
            result = await self._analyzer.analyze(request)
        except Exception as e:
            logger.error("vlm_analysis_failed", cluster_id=cluster_id, error=str(e))
            raise VLMAnalysisError(
                f"VLM analysis failed for cluster {cluster_id}: {e}"
            ) from e

        await self.persist_cluster_analysis(cluster_id, result)

        logger.info(
            "vlm_analysis_complete",
            cluster_id=cluster_id,
            anomaly_type=result.anomaly_type,
            is_false_alarm=result.is_false_alarm,
            confidence=result.confidence,
        )
        return result

    async def persist_cluster_analysis(
        self,
        cluster_id: str,
        result: VLMResult,
    ) -> Cluster:
        cluster = await self._cluster_repo.get_by_id(cluster_id)
        if cluster is None:
            raise NotFoundError("Cluster", cluster_id)

        cluster.vlm_analysis_json = json.dumps({
            "anomaly_type": result.anomaly_type,
            "is_false_alarm": result.is_false_alarm,
            "reason": result.reason,
            "confidence": result.confidence,
            "suggestion": result.suggestion,
            "raw_response": result.raw_response,
        })
        cluster.vlm_analyzed_at = datetime.now(tz=timezone.utc)
        await self._cluster_repo.update(cluster)
        await self._session.commit()
        return cluster

    async def batch_analyze_clusters(
        self, cluster_ids: list[str]
    ) -> dict[str, VLMResult]:
        results: dict[str, VLMResult] = {}
        for cluster_id in cluster_ids:
            try:
                results[cluster_id] = await self.analyze_cluster(cluster_id)
            except VLMAnalysisError:
                logger.warning("vlm_analysis_skipped", cluster_id=cluster_id)
        return results

    async def analyze_anomaly_by_id(self, anomaly_id: str) -> VLMResult:
        from app.repositories.anomaly.repository import AnomalyRepository

        repo = AnomalyRepository(self._session)
        anomaly = await repo.get_by_id(anomaly_id)
        if anomaly is None:
            raise NotFoundError("Anomaly", anomaly_id)

        return await self.analyze_single_anomaly(
            original_image_path=anomaly.original_path,
            roi_path=anomaly.roi_path,
            heatmap_path=anomaly.heatmap_path,
            crop_path=anomaly.crop_path,
        )

    async def analyze_single_anomaly(
        self,
        original_image_path: str | None = None,
        roi_path: str | None = None,
        heatmap_path: str | None = None,
        crop_path: str | None = None,
    ) -> VLMResult:
        request = VLMRequest(
            cluster_representative_paths=[
                p for p in [crop_path, roi_path, original_image_path, heatmap_path] if p is not None
            ],
        )
        return await self._analyzer.analyze(request)
