from __future__ import annotations

import io

from PIL import Image

from app.common.logging import get_logger
from app.infrastructure.queue.celery_app import celery_app
from app.infrastructure.storage.minio_client import minio_client

logger = get_logger(__name__)

THUMBNAIL_SIZE = (256, 256)


@celery_app.task(name="thumbnail.generate")
def generate_thumbnail(
    anomaly_id: str,
    source_path: str,
    label: str = "crop",
) -> dict[str, object]:
    """Generate thumbnail for anomaly images (crop, ROI, original).

    Thumbnails are used in the review UI for fast browsing.
    """
    logger.info("thumbnail_generation_started", anomaly_id=anomaly_id, label=label)

    try:
        data = minio_client.download(source_path)
        img = Image.open(io.BytesIO(data)).convert("RGB")
        img.thumbnail(THUMBNAIL_SIZE, Image.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        buf.seek(0)

        dir_parts = "/".join(source_path.split("/")[:-1])
        thumb_path = f"{dir_parts}/thumb_{anomaly_id}_{label}.jpg"

        minio_client.upload(thumb_path, buf.getvalue())

        logger.info("thumbnail_generated", anomaly_id=anomaly_id, path=thumb_path)
        return {
            "status": "completed",
            "anomaly_id": anomaly_id,
            "thumbnail_path": thumb_path,
        }
    except Exception as e:
        logger.error("thumbnail_generation_failed", anomaly_id=anomaly_id, error=str(e))
        return {
            "status": "failed",
            "anomaly_id": anomaly_id,
            "error": str(e),
        }


@celery_app.task(name="thumbnail.batch_generate")
def batch_generate_thumbnails(
    items: list[dict[str, str]],
) -> dict[str, object]:
    """Batch generate thumbnails for multiple anomaly images."""
    logger.info("batch_thumbnail_started", count=len(items))

    task_ids = []
    for item in items:
        result = generate_thumbnail.delay(
            anomaly_id=item["anomaly_id"],
            source_path=item["source_path"],
            label=item.get("label", "crop"),
        )
        task_ids.append(result.id)

    logger.info("batch_thumbnail_dispatched", task_count=len(task_ids))
    return {
        "status": "dispatched",
        "task_ids": task_ids,
        "total": len(task_ids),
    }
