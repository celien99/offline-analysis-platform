from __future__ import annotations

from io import BytesIO

from PIL import Image

from app.common.logging import get_logger
from app.infrastructure.queue.celery_app import celery_app
from app.infrastructure.storage.minio_client import minio_client
from app.workers import run_async

logger = get_logger(__name__)


@celery_app.task(name="thumbnail.generate")
def generate_thumbnail(
    anomaly_id: str,
    source_path: str,
    size: tuple[int, int] = (256, 256),
) -> dict[str, object]:
    logger.info("thumbnail_task_started", anomaly_id=anomaly_id, size=size)

    async def _run() -> dict[str, object]:
        raw = await minio_client.download(source_path)
        img = Image.open(BytesIO(raw)).convert("RGB")
        img.thumbnail(size, Image.LANCZOS)

        buf = BytesIO()
        img.save(buf, format="JPEG", quality=80)
        thumb_bytes = buf.getvalue()

        thumb_path = source_path.rsplit(".", 1)[0] + "_thumb.jpg"
        await minio_client.upload(thumb_path, thumb_bytes, "image/jpeg")

        logger.info("thumbnail_task_complete", anomaly_id=anomaly_id, path=thumb_path)
        return {"status": "completed", "anomaly_id": anomaly_id, "thumbnail_path": thumb_path}

    try:
        return run_async(_run())
    except Exception as e:
        logger.error("thumbnail_task_failed", anomaly_id=anomaly_id, error=str(e))
        return {"status": "failed", "anomaly_id": anomaly_id, "error": str(e)}
