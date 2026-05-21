from __future__ import annotations

import io

import numpy as np
from PIL import Image, ImageFilter

from app.common.logging import get_logger
from app.infrastructure.queue.celery_app import celery_app
from app.infrastructure.storage.minio_client import minio_client

logger = get_logger(__name__)


@celery_app.task(name="heatmap.generate")
def generate_heatmap(
    anomaly_id: str,
    original_path: str,
    roi_path: str | None = None,
) -> dict[str, object]:
    """Generate anomaly heatmap from original and ROI images.

    Uses Gaussian blur difference to highlight anomalous regions.
    Produces a heatmap overlay stored in MinIO.
    """
    logger.info("heatmap_generation_started", anomaly_id=anomaly_id)

    try:
        original_data = minio_client.download(original_path)
        original = Image.open(io.BytesIO(original_data)).convert("RGB")

        if roi_path:
            roi_data = minio_client.download(roi_path)
            roi = Image.open(io.BytesIO(roi_data)).convert("L")
            roi = roi.resize(original.size, Image.LANCZOS)
        else:
            roi = original.convert("L")

        blurred = roi.filter(ImageFilter.GaussianBlur(radius=15))
        diff = np.abs(np.array(roi, dtype=np.float32) - np.array(blurred, dtype=np.float32))
        diff = (diff - diff.min()) / (diff.max() - diff.min() + 1e-8) * 255
        diff = diff.astype(np.uint8)

        heatmap = Image.fromarray(diff)
        heatmap_colored = Image.merge("RGB", (
            heatmap,
            Image.fromarray(np.zeros_like(diff)),
            Image.fromarray(np.zeros_like(diff)),
        ))

        overlay = Image.blend(original, heatmap_colored, alpha=0.4)

        buf = io.BytesIO()
        overlay.save(buf, format="JPEG", quality=85)
        buf.seek(0)

        parts = original_path.split("/")
        date_folder = parts[1] if len(parts) > 1 else "unknown"
        camera_id = parts[2] if len(parts) > 2 else "unknown"
        heatmap_path = f"{'/'.join(parts[:3])}/heatmap_{anomaly_id}.jpg"

        minio_client.upload(heatmap_path, buf.getvalue())

        logger.info("heatmap_generated", anomaly_id=anomaly_id, path=heatmap_path)
        return {
            "status": "completed",
            "anomaly_id": anomaly_id,
            "heatmap_path": heatmap_path,
        }
    except Exception as e:
        logger.error("heatmap_generation_failed", anomaly_id=anomaly_id, error=str(e))
        return {
            "status": "failed",
            "anomaly_id": anomaly_id,
            "error": str(e),
        }
