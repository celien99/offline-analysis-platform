from __future__ import annotations

from io import BytesIO

import numpy as np
from PIL import Image

from app.common.logging import get_logger
from app.core.config import settings
from app.core.security import generate_uuid
from app.infrastructure.database.session import async_session_factory
from app.infrastructure.queue.celery_app import celery_app
from app.infrastructure.storage.minio_client import minio_client
from app.models.embedding import EmbeddingVector
from app.repositories.anomaly.repository import AnomalyRepository
from app.repositories.embedding.repository import EmbeddingRepository
from app.workers import run_async

logger = get_logger(__name__)

_extractor: object = None


def _get_extractor():
    global _extractor
    if _extractor is None:
        from ml.embedding.extractor import ResNet18EmbeddingExtractor

        _extractor = ResNet18EmbeddingExtractor(device="cpu")
    return _extractor


async def _process_embedding(anomaly_id: str, crop_path: str) -> dict[str, object]:
    raw = await minio_client.download(crop_path)
    image = np.array(Image.open(BytesIO(raw)).convert("RGB"))

    extractor = _get_extractor()
    vector = extractor.extract_sync(image)

    async with async_session_factory() as session:
        embedding_repo = EmbeddingRepository(session)
        existing = await embedding_repo.get_by_anomaly_id(anomaly_id)
        if existing is not None:
            logger.info("embedding_exists", anomaly_id=anomaly_id)
            return {"status": "skipped", "anomaly_id": anomaly_id}

        embedding = EmbeddingVector(
            id=generate_uuid(),
            anomaly_id=anomaly_id,
            embedding=vector.tolist(),
            model_name=extractor.model_name,
            model_version=settings.app_version,
            dimension=extractor.dimension,
        )
        await embedding_repo.create(embedding)

        anomaly_repo = AnomalyRepository(session)
        await anomaly_repo.update_status(anomaly_id, "embedded")

        await session.commit()

    logger.info("embedding_task_complete", anomaly_id=anomaly_id)
    return {"status": "completed", "anomaly_id": anomaly_id}


@celery_app.task(name="embedding.extract_for_anomaly")
def extract_embedding_for_anomaly(
    anomaly_id: str,
    crop_path: str,
) -> dict[str, object]:
    logger.info("embedding_task_started", anomaly_id=anomaly_id, crop_path=crop_path)
    try:
        return run_async(_process_embedding(anomaly_id, crop_path))
    except Exception as e:
        logger.error("embedding_task_failed", anomaly_id=anomaly_id, error=str(e))
        return {"status": "failed", "anomaly_id": anomaly_id, "error": str(e)}


@celery_app.task(name="embedding.batch_extract")
def batch_extract_embeddings(
    anomaly_batch: list[dict[str, str]],
) -> dict[str, object]:
    logger.info("batch_embedding_started", count=len(anomaly_batch))

    async def _batch() -> dict[str, object]:
        completed: list[dict[str, object]] = []
        failed: list[dict[str, object]] = []
        for item in anomaly_batch:
            try:
                result = await _process_embedding(
                    anomaly_id=item["anomaly_id"],
                    crop_path=item["crop_path"],
                )
                if result.get("status") in ("completed", "skipped"):
                    completed.append(result)
                else:
                    failed.append(result)
            except Exception as e:
                logger.error(
                    "batch_embedding_item_failed",
                    anomaly_id=item.get("anomaly_id"),
                    error=str(e),
                )
                failed.append({"anomaly_id": item.get("anomaly_id"), "error": str(e)})
        return {
            "status": "completed" if not failed else "partial",
            "completed": len(completed),
            "failed": len(failed),
            "results": completed,
            "errors": failed,
        }

    return run_async(_batch())
