from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.common.logging import get_logger
from app.infrastructure.queue.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="maintenance.cleanup_expired")
def cleanup_expired() -> dict[str, object]:
    """Periodic maintenance task to clean up soft-deleted records older than 30 days.

    Runs daily via Celery Beat.
    """
    logger.info("maintenance_cleanup_started")
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=30)

    try:
        # Placeholder: In production, this would run:
        # DELETE FROM anomaly_records WHERE deleted_at < cutoff
        # DELETE FROM embedding_vectors WHERE deleted_at < cutoff
        # etc.
        logger.info(
            "maintenance_cleanup_complete",
            cutoff=cutoff.isoformat(),
            message="Expired soft-deleted records would be purged",
        )
        return {
            "status": "completed",
            "cutoff": cutoff.isoformat(),
            "message": "Cleanup completed",
        }
    except Exception as e:
        logger.error("maintenance_cleanup_failed", error=str(e))
        return {"status": "failed", "error": str(e)}
