from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.logging import get_logger
from app.core.exceptions import NotFoundError
from app.core.security import generate_trace_id, generate_uuid
from app.infrastructure.storage.minio_client import MinIOClient
from app.models.anomaly import AnomalyRecord
from app.repositories.anomaly.repository import AnomalyRepository
from app.repositories.cluster.repository import ClusterMembershipRepository
from app.repositories.embedding.repository import EmbeddingRepository

logger = get_logger(__name__)


class AnomalyService:
    """异常记录管理：入库、查询、删除、重新处理。"""

    def __init__(self, session: AsyncSession, minio: MinIOClient) -> None:
        self._session = session
        self._minio = minio
        self._repo = AnomalyRepository(session)

    async def create_anomaly_with_files(
        self,
        *,
        camera_id: str,
        seat_model_id: str | None = None,
        region_id: str | None = None,
        source: str = "patchcore",
        anomaly_score: float | None = None,
        date_folder: str,
        detected_at: datetime,
        decision_reason: str | None = None,
        filter_confidence: float | None = None,
        filter_real_defect_score: float | None = None,
        filter_false_alarm_score: float | None = None,
        filter_class_id: int | None = None,
        filter_action: str | None = None,
        original_data: bytes | None = None,
        heatmap_data: bytes | None = None,
        crop_data_list: list[bytes] | None = None,
        original_content_type: str = "image/jpeg",
        heatmap_content_type: str = "image/jpeg",
    ) -> list[AnomalyRecord]:
        """创建异常记录并上传文件到 MinIO，然后触发 Celery 流水线。"""
        trace_id = generate_trace_id()
        batch_id = generate_uuid()
        base_path = f"anomaly_data/{date_folder}/{camera_id}/{batch_id}"

        async def _save(data: bytes | None, suffix: str, ct: str = "image/jpeg") -> str | None:
            if data is None:
                return None
            path = f"{base_path}_{suffix}.jpg"
            await self._minio.upload(path, data, ct)
            return path

        original_path = await _save(original_data, "original", original_content_type)
        heatmap_path = await _save(heatmap_data, "heatmap", heatmap_content_type)

        anomalies: list[AnomalyRecord] = []
        for i, crop_data in enumerate(crop_data_list or []):
            crop_path = await _save(crop_data, f"crop_{i}")
            if not crop_path:
                continue

            anomaly_id = generate_uuid()
            anomaly = AnomalyRecord(
                id=anomaly_id,
                camera_id=camera_id,
                seat_model_id=seat_model_id,
                region_id=region_id,
                source=source,
                anomaly_score=anomaly_score,
                date_folder=date_folder,
                detected_at=detected_at,
                decision_reason=decision_reason,
                filter_confidence=filter_confidence,
                filter_real_defect_score=filter_real_defect_score,
                filter_false_alarm_score=filter_false_alarm_score,
                filter_class_id=filter_class_id,
                filter_action=filter_action,
                original_path=original_path,
                heatmap_path=heatmap_path,
                crop_path=crop_path,
                crop_paths=json.dumps([crop_path]),
                status="pending",
                trace_id=trace_id,
            )
            await self._repo.create(anomaly)
            anomalies.append(anomaly)

        if not anomalies:
            anomaly_id = generate_uuid()
            anomaly = AnomalyRecord(
                id=anomaly_id,
                camera_id=camera_id,
                seat_model_id=seat_model_id,
                region_id=region_id,
                source=source,
                anomaly_score=anomaly_score,
                date_folder=date_folder,
                detected_at=detected_at,
                decision_reason=decision_reason,
                filter_confidence=filter_confidence,
                filter_real_defect_score=filter_real_defect_score,
                filter_false_alarm_score=filter_false_alarm_score,
                filter_class_id=filter_class_id,
                filter_action=filter_action,
                original_path=original_path,
                heatmap_path=heatmap_path,
                crop_path=None,
                crop_paths=None,
                status="pending",
                trace_id=trace_id,
            )
            await self._repo.create(anomaly)
            anomalies.append(anomaly)

        logger.info(
            "anomaly_created_with_files",
            batch_id=batch_id,
            trace_id=trace_id,
            anomaly_count=len(anomalies),
            has_original=original_path is not None,
            crop_input_count=len(crop_data_list or []),
        )

        # 通过 Celery pipeline 异步处理：embedding → clustering → VLM
        from app.services.pipeline.service import PipelineService
        pipeline = PipelineService()
        pipeline.dispatch_for_new_anomalies()

        return anomalies

    async def list_anomalies(
        self,
        *,
        camera_id: str | None = None,
        seat_model_id: str | None = None,
        region_id: str | None = None,
        source: str | None = None,
        status: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[AnomalyRecord], int]:
        records = await self._repo.list_all(
            camera_id=camera_id,
            seat_model_id=seat_model_id,
            region_id=region_id,
            source=source,
            status=status,
            offset=offset,
            limit=limit,
        )
        total = await self._repo.count(
            camera_id=camera_id,
            seat_model_id=seat_model_id,
            region_id=region_id,
            source=source,
            status=status,
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
        # 级联清理 embedding 和 membership，避免孤儿数据污染后续聚类
        embedding_repo = EmbeddingRepository(self._session)
        existing_embedding = await embedding_repo.get_by_anomaly_id(anomaly_id)
        if existing_embedding is not None:
            await embedding_repo.soft_delete(existing_embedding.id)
        membership_repo = ClusterMembershipRepository(self._session)
        await membership_repo.soft_delete_by_anomaly_id(anomaly_id)
        await self._repo.soft_delete(anomaly_id)
        logger.info("anomaly_soft_deleted", anomaly_id=anomaly_id)

    async def reprocess_anomaly(self, anomaly_id: str) -> AnomalyRecord:
        """重置异常状态并触发 Celery pipeline 重新处理。

        清理已有嵌入向量和聚类归属，确保 embedding worker 不会因去重逻辑跳过。
        """
        record = await self._repo.get_by_id(anomaly_id)
        if record is None:
            raise NotFoundError("Anomaly", anomaly_id)

        # 软删除已有嵌入向量，否则 embedding worker 会因为 unique 约束跳过
        embedding_repo = EmbeddingRepository(self._session)
        existing_embedding = await embedding_repo.get_by_anomaly_id(anomaly_id)
        if existing_embedding is not None:
            await embedding_repo.soft_delete(existing_embedding.id)
            logger.info("reprocess_embedding_cleared", anomaly_id=anomaly_id)

        # 软删除已有聚类归属
        membership_repo = ClusterMembershipRepository(self._session)
        deleted_count = await membership_repo.soft_delete_by_anomaly_id(anomaly_id)
        if deleted_count > 0:
            logger.info(
                "reprocess_membership_cleared",
                anomaly_id=anomaly_id,
                deleted_count=deleted_count,
            )

        await self._repo.update_status(anomaly_id, "pending")
        await self._session.commit()
        await self._session.refresh(record)

        logger.info("anomaly_reprocess_start", anomaly_id=anomaly_id)
        from app.services.pipeline.service import PipelineService
        pipeline = PipelineService()
        # 只对该 anomaly 提取 embedding + 对所有非 reviewed 做增量聚类，
        # 避免 dispatch_for_new_anomalies 拉入其他 pending 异常导致全量扫描
        if record.crop_path:
            pipeline.dispatch_single_reprocess(anomaly_id, record.crop_path)
        else:
            logger.warning("reprocess_no_crop_path", anomaly_id=anomaly_id)
        return record
