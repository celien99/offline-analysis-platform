from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, get_vlm_analyzer
from app.common.logging import get_logger
from app.domain.multimodal import VLMAnalyzer
from app.schemas.multimodal import (
    VLMAnalyzeRequest,
    VLMAnomalyAnalysisResponse,
    VLMAnalysisResponse,
    VLMBatchAnalysisResponse,
    VLMResultResponse,
)
from app.services.multimodal.service import VLMService

router = APIRouter(prefix="/api/multimodal", tags=["multimodal"])
logger = get_logger(__name__)


@router.post("/analyze/cluster/{cluster_id}", response_model=VLMAnalysisResponse)
async def analyze_cluster(
    cluster_id: str,
    session: AsyncSession = Depends(get_session),
    analyzer: VLMAnalyzer = Depends(get_vlm_analyzer),
) -> VLMAnalysisResponse:
    service = VLMService(session, analyzer)
    try:
        result = await service.analyze_cluster(cluster_id)
        return VLMAnalysisResponse(
            status="completed",
            cluster_id=cluster_id,
            result=VLMResultResponse(
                anomaly_type=result.anomaly_type,
                is_false_alarm=result.is_false_alarm,
                reason=result.reason,
                confidence=result.confidence,
                suggestion=result.suggestion,
                raw_response=result.raw_response,
            ),
        )
    except Exception as e:
        logger.error("vlm_api_analysis_failed", cluster_id=cluster_id, error=str(e))
        return VLMAnalysisResponse(
            status="failed",
            cluster_id=cluster_id,
            error=str(e),
        )


@router.post("/analyze/batch", response_model=VLMBatchAnalysisResponse)
async def analyze_clusters_batch(
    request: VLMAnalyzeRequest,
    session: AsyncSession = Depends(get_session),
    analyzer: VLMAnalyzer = Depends(get_vlm_analyzer),
) -> VLMBatchAnalysisResponse:
    service = VLMService(session, analyzer)
    results_map = await service.batch_analyze_clusters(request.cluster_ids)

    results: list[VLMAnalysisResponse] = []
    for cid, vlm_result in results_map.items():
        results.append(
            VLMAnalysisResponse(
                status="completed",
                cluster_id=cid,
                result=VLMResultResponse(
                    anomaly_type=vlm_result.anomaly_type,
                    is_false_alarm=vlm_result.is_false_alarm,
                    reason=vlm_result.reason,
                    confidence=vlm_result.confidence,
                    suggestion=vlm_result.suggestion,
                    raw_response=vlm_result.raw_response,
                ),
            )
        )

    return VLMBatchAnalysisResponse(
        status="completed",
        total=len(results),
        results=results,
    )


@router.post(
    "/analyze/anomaly/{anomaly_id}", response_model=VLMAnomalyAnalysisResponse
)
async def analyze_anomaly(
    anomaly_id: str,
    session: AsyncSession = Depends(get_session),
    analyzer: VLMAnalyzer = Depends(get_vlm_analyzer),
) -> VLMAnomalyAnalysisResponse:
    from app.repositories.anomaly.repository import AnomalyRepository

    repo = AnomalyRepository(session)
    anomaly = await repo.get_by_id(anomaly_id)
    if anomaly is None:
        return VLMAnomalyAnalysisResponse(
            status="failed",
            anomaly_id=anomaly_id,
            error=f"Anomaly {anomaly_id} not found",
        )

    service = VLMService(session, analyzer)
    try:
        result = await service.analyze_single_anomaly(
            original_image_path=anomaly.original_path,
            roi_path=anomaly.roi_path,
            heatmap_path=anomaly.heatmap_path,
            crop_path=anomaly.crop_path,
        )
        return VLMAnomalyAnalysisResponse(
            status="completed",
            anomaly_id=anomaly_id,
            result=VLMResultResponse(
                anomaly_type=result.anomaly_type,
                is_false_alarm=result.is_false_alarm,
                reason=result.reason,
                confidence=result.confidence,
                suggestion=result.suggestion,
                raw_response=result.raw_response,
            ),
        )
    except Exception as e:
        logger.error(
            "vlm_anomaly_analysis_failed", anomaly_id=anomaly_id, error=str(e)
        )
        return VLMAnomalyAnalysisResponse(
            status="failed",
            anomaly_id=anomaly_id,
            error=str(e),
        )
