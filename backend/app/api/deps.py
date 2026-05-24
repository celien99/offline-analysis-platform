from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.embedding import EmbeddingExtractor
from app.domain.multimodal import VLMAnalyzer
from app.infrastructure.database.session import get_db
from app.infrastructure.storage.minio_client import MinIOClient, minio_client

_vlm_analyzer: VLMAnalyzer | None = None
_embedding_extractor: EmbeddingExtractor | None = None


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db():
        yield session


def get_minio() -> MinIOClient:
    return minio_client


def get_vlm_analyzer() -> VLMAnalyzer:
    global _vlm_analyzer
    if _vlm_analyzer is None:
        from app.core.config import settings
        from ml.vlm.analyzer import QwenVLMAnalyzer

        _vlm_analyzer = QwenVLMAnalyzer(
            endpoint=settings.vlm_endpoint,
            model_name=settings.vlm_model,
            api_key=settings.vlm_api_key,
        )
    return _vlm_analyzer


def get_embedding_extractor() -> EmbeddingExtractor:
    global _embedding_extractor
    if _embedding_extractor is None:
        from app.core.config import settings
        from ml.embedding.dino_extractor import DINOv2EmbeddingExtractor

        _embedding_extractor = DINOv2EmbeddingExtractor(
            model_name=settings.embedding_model,
            device="cpu",
        )
    return _embedding_extractor
