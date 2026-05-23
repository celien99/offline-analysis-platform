from __future__ import annotations

import json
from datetime import datetime, timezone

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
        await self._session.commit()
        await self._session.refresh(record)

        # 本地开发模式：直接在 API 进程内同步执行 pipeline
        # （Celery worker 仅用于生产部署）
        logger.info("anomaly_reprocess_start", anomaly_id=anomaly_id)
        await self._run_pipeline_sync(record)
        return record

    async def _run_pipeline_sync(self, anomaly: AnomalyRecord) -> None:
        """同步执行单条 anomaly 的 embedding → clustering 流水线。"""
        import asyncio
        from io import BytesIO

        import numpy as np
        from PIL import Image

        from app.repositories.cluster.repository import ClusterMembershipRepository, ClusterRepository
        from app.repositories.embedding.repository import EmbeddingRepository

        # 1. Embedding
        crop_path = anomaly.crop_path or anomaly.roi_path
        if not crop_path:
            logger.warning("pipeline_no_image", anomaly_id=anomaly.id)
            return

        try:
            raw = await self._minio.download(crop_path)
            image = np.array(Image.open(BytesIO(raw)).convert("RGB"))
        except Exception as e:
            logger.error("pipeline_download_failed", anomaly_id=anomaly.id, error=str(e))
            return

        try:
            from ml.embedding.extractor import ResNet18EmbeddingExtractor
            extractor = ResNet18EmbeddingExtractor(device="cpu")
            vector = extractor.extract_sync(image)
        except Exception as e:
            logger.error("pipeline_embedding_failed", anomaly_id=anomaly.id, error=str(e))
            return

        from app.core.security import generate_uuid
        from app.models.embedding import EmbeddingVector

        embedding_repo = EmbeddingRepository(self._session)
        existing_emb = await embedding_repo.get_by_anomaly_id(anomaly.id)
        if existing_emb is not None:
            # 已有 embedding 则跳过创建，仅更新状态
            logger.info("pipeline_embedding_exists", anomaly_id=anomaly.id)
            await self._repo.update_status(anomaly.id, "embedded")
        else:
            embedding = EmbeddingVector(
                id=generate_uuid(),
                anomaly_id=anomaly.id,
                embedding=vector.tolist(),
                model_name=extractor.model_name,
                model_version="local",
                dimension=extractor.dimension,
            )
            await embedding_repo.create(embedding)
            await self._repo.update_status(anomaly.id, "embedded")
            logger.info("pipeline_embedding_done", anomaly_id=anomaly.id)

        # 2. Clustering（收集所有 embedded anomalies 进行聚类）
        try:
            all_embeddings = await embedding_repo.get_all_embeddings_with_ids()
            if len(all_embeddings) < 3:
                logger.info("pipeline_clustering_skip", count=len(all_embeddings))
                await self._session.commit()
                return

            embeddings_map: dict[str, np.ndarray] = {
                aid: np.array(vec, dtype=np.float32) for aid, vec in all_embeddings
            }

            from ml.clustering.pipeline import ClusteringPipeline
            pipeline_cls = ClusteringPipeline(
                umap_n_components=2,
                umap_n_neighbors=min(15, len(all_embeddings) - 1),
                umap_min_dist=0.1,
                hdbscan_min_cluster_size=3,
                hdbscan_min_samples=1,
            )
            ids = list(embeddings_map.keys())
            matrix = np.stack([embeddings_map[i] for i in ids])
            result = pipeline_cls.fit_predict(matrix, ids)

            labels = result["labels"]
            probabilities = result["probabilities"]
            umap_coords = result["umap_coords"]
            representatives = pipeline_cls.get_representatives(labels, probabilities, n_per_cluster=5)

            cluster_repo = ClusterRepository(self._session)
            membership_repo = ClusterMembershipRepository(self._session)

            for label in sorted(set(int(lb) for lb in labels)):
                if label == -1:
                    continue
                label_indices = [i for i, lb in enumerate(labels) if int(lb) == label]
                rep_indices = representatives.get(label, [])
                rep_ids = [ids[i] for i in rep_indices] if rep_indices else []

                from app.models.cluster import Cluster, ClusterMembership
                cluster = Cluster(
                    id=generate_uuid(),
                    hdbscan_label=label,
                    sample_count=len(label_indices),
                    representative_ids=json.dumps(rep_ids),
                    centroid=json.dumps(matrix[label_indices].mean(axis=0).tolist()),
                    umap_x=float(umap_coords[label_indices].mean(axis=0)[0]),
                    umap_y=float(umap_coords[label_indices].mean(axis=0)[1]),
                    hdbscan_probability=float(probabilities[label_indices].mean()),
                    status="pending_review",
                    clustering_run_at=datetime.now(tz=timezone.utc),
                )
                await cluster_repo.create(cluster)

                memberships = [
                    ClusterMembership(
                        id=generate_uuid(),
                        cluster_id=cluster.id,
                        anomaly_id=ids[i],
                        membership_score=float(probabilities[i]),
                    )
                    for i in label_indices
                ]
                await membership_repo.bulk_create(memberships)

                for i in label_indices:
                    await self._repo.update_status(ids[i], "clustered")

            await self._session.commit()
            logger.info("pipeline_clustering_done", num_clusters=len(set(lb for lb in labels if lb != -1)))

        except Exception as e:
            logger.error("pipeline_clustering_failed", error=str(e))
