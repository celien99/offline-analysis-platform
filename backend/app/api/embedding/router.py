from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_minio, get_session
from app.common.logging import get_logger
from app.infrastructure.storage.minio_client import MinIOClient
from app.repositories.anomaly.repository import AnomalyRepository
from app.schemas.embedding import EmbeddingSimilarResult, EmbeddingSearchByVectorRequest
from app.schemas.common import ErrorResponse
from app.services.embedding.service import EmbeddingService

router = APIRouter(prefix="/api/embedding", tags=["embedding"])
logger = get_logger(__name__)


async def _enrich_results(
    results: list[dict[str, object]],
    session: AsyncSession,
    minio: MinIOClient,
) -> list[EmbeddingSimilarResult]:
    """用 AnomalyRecord 的 camera_id/date_folder/crop_url 丰富搜索结果。"""
    anomaly_ids = [str(r.get("anomaly_id", "")) for r in results if r.get("anomaly_id")]
    if not anomaly_ids:
        return [
            EmbeddingSimilarResult(
                anomaly_id=str(r.get("anomaly_id", "")),
                similarity=float(r.get("similarity", 0.0)),
            )
            for r in results
        ]

    anomaly_repo = AnomalyRepository(session)
    anomalies = await anomaly_repo.get_by_ids(anomaly_ids)
    id_to_anomaly = {a.id: a for a in anomalies}

    enriched: list[EmbeddingSimilarResult] = []
    for r in results:
        aid = str(r.get("anomaly_id", ""))
        anomaly = id_to_anomaly.get(aid)
        crop_url: str | None = None
        if anomaly and anomaly.crop_path:
            try:
                crop_url = await minio.get_presigned_url(anomaly.crop_path, expires_seconds=3600)
            except Exception:
                crop_url = None

        enriched.append(EmbeddingSimilarResult(
            anomaly_id=aid,
            similarity=float(r.get("similarity", 0.0)),
            seat_model_id=anomaly.seat_model_id if anomaly else None,
            camera_id=anomaly.camera_id if anomaly else None,
            region_id=anomaly.region_id if anomaly else None,
            date_folder=anomaly.date_folder if anomaly else None,
            crop_url=crop_url,
        ))

    return enriched


@router.get(
    "/search",
    response_model=list[EmbeddingSimilarResult],
    responses={404: {"model": ErrorResponse}},
)
async def search_similar_embeddings(
    anomaly_id: str = Query(..., description="Query anomaly ID"),
    top_k: int = Query(default=20, ge=1, le=100),
    threshold: float = Query(default=0.7, ge=0.0, le=1.0),
    session: AsyncSession = Depends(get_session),
    minio: MinIOClient = Depends(get_minio),
) -> list[EmbeddingSimilarResult]:
    service = EmbeddingService(session)
    results = await service.find_similar_anomalies(
        anomaly_id=anomaly_id,
        top_k=top_k,
        threshold=threshold,
    )
    return await _enrich_results(results, session, minio)


@router.post(
    "/search",
    response_model=list[EmbeddingSimilarResult],
)
async def search_by_vector(
    request: EmbeddingSearchByVectorRequest,
    session: AsyncSession = Depends(get_session),
    minio: MinIOClient = Depends(get_minio),
) -> list[EmbeddingSimilarResult]:
    service = EmbeddingService(session)
    results = await service.find_similar_by_vector(
        query_vector=request.vector,
        top_k=request.top_k,
        threshold=request.threshold,
        seat_model_id=request.seat_model_id,
        camera_id=request.camera_id,
        region_id=request.region_id,
    )
    return await _enrich_results(results, session, minio)
