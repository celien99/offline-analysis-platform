from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.logging import get_logger
from app.core.exceptions import NotFoundError, VLMAnalysisError
from app.domain.multimodal import VLMAnalyzer, VLMRequest, VLMResult
from app.repositories.cluster.repository import ClusterMembershipRepository, ClusterRepository

logger = get_logger(__name__)


class VLMService:
    def __init__(
        self,
        session: AsyncSession,
        analyzer: VLMAnalyzer,
    ) -> None:
        self._session = session
        self._analyzer = analyzer
        self._cluster_repo = ClusterRepository(session)
        self._membership_repo = ClusterMembershipRepository(session)

    async def analyze_cluster(self, cluster_id: str) -> VLMResult:
        cluster = await self._cluster_repo.get_by_id(cluster_id)
        if cluster is None:
            raise NotFoundError("Cluster", cluster_id)

        import json

        representative_ids = json.loads(cluster.representative_ids or "[]")

        request = VLMRequest(
            cluster_representative_paths=representative_ids,
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

        logger.info(
            "vlm_analysis_complete",
            cluster_id=cluster_id,
            anomaly_type=result.anomaly_type,
            is_false_alarm=result.is_false_alarm,
            confidence=result.confidence,
        )
        return result

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

    async def analyze_single_anomaly(
        self,
        original_image_path: str | None = None,
        roi_path: str | None = None,
        heatmap_path: str | None = None,
        crop_path: str | None = None,
    ) -> VLMResult:
        request = VLMRequest(
            cluster_representative_paths=[
                p for p in [crop_path, roi_path, original_image_path] if p is not None
            ],
        )
        return await self._analyzer.analyze(request)
