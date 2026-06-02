from __future__ import annotations

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.logging import get_logger
from app.core.config import settings
from app.core.exceptions import EmbeddingGenerationError, NotFoundError
from app.core.security import generate_uuid
from app.domain.embedding import EmbeddingExtractor
from app.models.embedding import EmbeddingVector
from app.repositories.embedding.repository import EmbeddingRepository

logger = get_logger(__name__)


class EmbeddingService:
    def __init__(
        self,
        session: AsyncSession,
        extractor: EmbeddingExtractor | None = None,
    ) -> None:
        self._session = session
        self._repo = EmbeddingRepository(session)
        self._extractor = extractor

    async def generate_embedding(
        self,
        anomaly_id: str,
        image: np.ndarray,
        *,
        region_id: str | None = None,
        model_version: str | None = None,
    ) -> EmbeddingVector:
        if self._extractor is None:
            raise EmbeddingGenerationError(
                "No embedding extractor configured"
            )
        try:
            vector = await self._extractor.extract(image)
        except Exception as e:
            logger.error("embedding_generation_failed", anomaly_id=anomaly_id, error=str(e))
            raise EmbeddingGenerationError(
                f"Failed to generate embedding for {anomaly_id}: {e}"
            ) from e

        embedding = EmbeddingVector(
            id=generate_uuid(),
            anomaly_id=anomaly_id,
            region_id=region_id,
            embedding=vector.tolist(),
            model_name=self._extractor.model_name,
            model_version=model_version or settings.app_version,
            dimension=self._extractor.dimension,
        )
        return await self._repo.create(embedding)

    async def get_embedding(self, anomaly_id: str) -> EmbeddingVector:
        result = await self._repo.get_by_anomaly_id(anomaly_id)
        if result is None:
            raise NotFoundError("EmbeddingVector", anomaly_id)
        return result

    async def find_similar_anomalies(
        self,
        anomaly_id: str,
        *,
        top_k: int = 20,
        threshold: float = 0.7,
    ) -> list[dict[str, object]]:
        return await self._repo.find_similar_by_anomaly(
            anomaly_id=anomaly_id,
            top_k=top_k,
            threshold=threshold,
        )

    async def find_similar_by_vector(
        self,
        query_vector: list[float],
        *,
        top_k: int = 20,
        threshold: float = 0.7,
        seat_model_id: str | None = None,
        camera_id: str | None = None,
        region_id: str | None = None,
        region_id_is_null: bool = False,
    ) -> list[dict[str, object]]:
        return await self._repo.find_similar(
            query_vector=query_vector,
            top_k=top_k,
            threshold=threshold,
            seat_model_id=seat_model_id,
            camera_id=camera_id,
            region_id=region_id,
            region_id_is_null=region_id_is_null,
        )

    async def batch_generate(
        self,
        anomaly_images: list[tuple[str, np.ndarray]],
        *,
        model_version: str | None = None,
    ) -> list[EmbeddingVector]:
        embeddings: list[EmbeddingVector] = []
        for anomaly_id, image in anomaly_images:
            emb = await self.generate_embedding(
                anomaly_id, image, model_version=model_version
            )
            embeddings.append(emb)
        return embeddings
