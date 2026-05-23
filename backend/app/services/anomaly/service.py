from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.logging import get_logger
from app.core.exceptions import NotFoundError
from app.core.security import generate_trace_id, generate_uuid
from app.infrastructure.storage.minio_client import MinIOClient
from app.models.anomaly import AnomalyRecord
from app.repositories.anomaly.repository import AnomalyRepository

logger = get_logger(__name__)


class AnomalyService:
    def __init__(self, session: AsyncSession, minio: MinIOClient) -> None:
        self._session = session
        self._minio = minio
        self._repo = AnomalyRepository(session)

    async def create_anomaly(
        self,
        *,
        camera_id: str,
        source: str = "patchcore",
        anomaly_score: float | None = None,
        date_folder: str,
        detected_at: datetime,
        metadata_json: str | None = None,
    ) -> AnomalyRecord:
        trace_id = generate_trace_id()
        logger.info("anomaly_upload", camera_id=camera_id, trace_id=trace_id)

        anomaly = AnomalyRecord(
            id=generate_uuid(),
            camera_id=camera_id,
            source=source,
            anomaly_score=anomaly_score,
            date_folder=date_folder,
            detected_at=detected_at,
            metadata_json=metadata_json,
            status="pending",
            trace_id=trace_id,
        )
        await self._repo.create(anomaly)

        logger.info("anomaly_created", anomaly_id=anomaly.id, trace_id=trace_id)
        return anomaly

    async def create_anomaly_with_files(
        self,
        *,
        camera_id: str,
        source: str = "patchcore",
        anomaly_score: float | None = None,
        date_folder: str,
        detected_at: datetime,
        original_data: bytes | None = None,
        roi_data: bytes | None = None,
        heatmap_data: bytes | None = None,
        crop_data: bytes | None = None,
        original_content_type: str = "image/jpeg",
        roi_content_type: str = "image/jpeg",
        heatmap_content_type: str = "image/jpeg",
        crop_content_type: str = "image/jpeg",
    ) -> AnomalyRecord:
        trace_id = generate_trace_id()
        anomaly_id = generate_uuid()

        base_path = f"anomaly_data/{date_folder}/{camera_id}/{anomaly_id}"

        async def _save(data: bytes | None, suffix: str, ct: str) -> str | None:
            if data is None:
                return None
            path = f"{base_path}_{suffix}.jpg"
            await self._minio.upload(path, data, ct)
            return path

        original_path = await _save(original_data, "original", original_content_type)
        roi_path = await _save(roi_data, "roi", roi_content_type)
        heatmap_path = await _save(heatmap_data, "heatmap", heatmap_content_type)
        crop_path = await _save(crop_data, "crop", crop_content_type)

        anomaly = AnomalyRecord(
            id=anomaly_id,
            camera_id=camera_id,
            source=source,
            anomaly_score=anomaly_score,
            date_folder=date_folder,
            detected_at=detected_at,
            original_path=original_path,
            roi_path=roi_path,
            heatmap_path=heatmap_path,
            crop_path=crop_path,
            status="pending",
            trace_id=trace_id,
        )
        await self._repo.create(anomaly)

        logger.info(
            "anomaly_created_with_files",
            anomaly_id=anomaly.id,
            trace_id=trace_id,
            has_original=original_path is not None,
            has_crop=crop_path is not None,
        )
        return anomaly

    async def list_anomalies(
        self,
        *,
        camera_id: str | None = None,
        source: str | None = None,
        status: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[AnomalyRecord], int]:
        records = await self._repo.list_all(
            camera_id=camera_id,
            source=source,
            status=status,
            offset=offset,
            limit=limit,
        )
        total = await self._repo.count(
            camera_id=camera_id, source=source, status=status
        )
        return list(records), total

    async def get_anomaly(self, anomaly_id: str) -> AnomalyRecord:
        record = await self._repo.get_by_id(anomaly_id)
        if record is None:
            raise NotFoundError("Anomaly", anomaly_id)
        return record

    async def soft_delete_anomaly(self, anomaly_id: str) -> None:
        record = await self._repo.get_by_id(anomaly_id)
        if record is None:
            raise NotFoundError("Anomaly", anomaly_id)
        await self._repo.soft_delete(anomaly_id)
        logger.info("anomaly_soft_deleted", anomaly_id=anomaly_id)

    async def reprocess_anomaly(self, anomaly_id: str) -> AnomalyRecord:
        record = await self._repo.get_by_id(anomaly_id)
        if record is None:
            raise NotFoundError("Anomaly", anomaly_id)
        await self._repo.update_status(anomaly_id, "pending")
        # 触发 pipeline 重新处理该异常
        from app.workers.pipeline_worker.tasks import process_new_anomalies
        process_new_anomalies.delay(limit=500)
        logger.info("anomaly_reprocess_queued", anomaly_id=anomaly_id)
        return record
