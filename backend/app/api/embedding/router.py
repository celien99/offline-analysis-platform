from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.common.logging import get_logger
from app.schemas.embedding import EmbeddingSimilarResult, EmbeddingSearchByVectorRequest
from app.schemas.common import ErrorResponse
from app.services.embedding.service import EmbeddingService

router = APIRouter(prefix="/api/embedding", tags=["embedding"])
logger = get_logger(__name__)


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
) -> list[EmbeddingSimilarResult]:
    service = EmbeddingService(session)
    results = await service.find_similar_anomalies(
        anomaly_id=anomaly_id,
        top_k=top_k,
        threshold=threshold,
    )
    return [
        EmbeddingSimilarResult(
            anomaly_id=str(r.get("anomaly_id", "")),
            similarity=float(r.get("similarity", 0.0)),
        )
        for r in results
    ]


@router.post(
    "/search",
    response_model=list[EmbeddingSimilarResult],
)
async def search_by_vector(
    request: EmbeddingSearchByVectorRequest,
    session: AsyncSession = Depends(get_session),
) -> list[EmbeddingSimilarResult]:
    service = EmbeddingService(session)
    results = await service.find_similar_by_vector(
        query_vector=request.vector,
        top_k=request.top_k,
        threshold=request.threshold,
    )
    return [
        EmbeddingSimilarResult(
            anomaly_id=str(r.get("anomaly_id", "")),
            similarity=float(r.get("similarity", 0.0)),
        )
        for r in results
    ]
