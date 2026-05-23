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
        heatmap_data: bytes | None = None,
        crop_data_list: list[bytes] | None = None,
        original_content_type: str = "image/jpeg",
        heatmap_content_type: str = "image/jpeg",
    ) -> list[AnomalyRecord]:
        """创建异常记录：每个异常 patch 独立为一条记录。

        PatchCore 在一张图中可能发现多处离散异常区域，
        每处异常作为一个独立的 AnomalyRecord 参与后续聚类。
        """
        trace_id = generate_trace_id()
        batch_id = generate_uuid()  # 同一批上传的批次标识

        base_path = f"anomaly_data/{date_folder}/{camera_id}/{batch_id}"

        async def _save(data: bytes | None, suffix: str, ct: str = "image/jpeg") -> str | None:
            if data is None:
                return None
            path = f"{base_path}_{suffix}.jpg"
            await self._minio.upload(path, data, ct)
            return path

        original_path = await _save(original_data, "original", original_content_type)
        heatmap_path = await _save(heatmap_data, "heatmap", heatmap_content_type)

        # 每个 crop 独立为一条 anomaly 记录
        anomalies: list[AnomalyRecord] = []
        for i, crop_data in enumerate(crop_data_list or []):
            crop_path = await _save(crop_data, f"crop_{i}")
            if not crop_path:
                continue

            anomaly_id = generate_uuid()
            anomaly = AnomalyRecord(
                id=anomaly_id,
                camera_id=camera_id,
                source=source,
                anomaly_score=anomaly_score,
                date_folder=date_folder,
                detected_at=detected_at,
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
            # 无 crop 时仍创建一条记录（用于追溯检测事件）
            anomaly_id = generate_uuid()
            anomaly = AnomalyRecord(
                id=anomaly_id,
                camera_id=camera_id,
                source=source,
                anomaly_score=anomaly_score,
                date_folder=date_folder,
                detected_at=detected_at,
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

        # 批量 pipeline：embedding 并行 → 聚类一次
        self._schedule_pipeline([a.id for a in anomalies])

        return anomalies

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

        logger.info("anomaly_reprocess_start", anomaly_id=anomaly_id)
        await self._extract_embedding(record)
        await self._run_clustering()
        return record

    @staticmethod
    def _schedule_pipeline(anomaly_ids: list[str]) -> None:
        """后台：逐条提取 embedding，最后统一聚类。"""
        import asyncio
        from app.infrastructure.database.session import async_session_factory

        async def _bg() -> None:
            async with async_session_factory() as bg_session:
                from app.repositories.anomaly.repository import AnomalyRepository
                from app.infrastructure.storage.minio_client import minio_client
                repo = AnomalyRepository(bg_session)
                service = AnomalyService(bg_session, minio_client)

                # 1) 为每个 patch 独立提取 embedding
                for aid in anomaly_ids:
                    anomaly = await repo.get_by_id(aid)
                    if anomaly is None or not anomaly.crop_path:
                        continue
                    await service._extract_embedding(anomaly)

                # 2) 统一跑一次聚类
                await service._run_clustering()

        asyncio.create_task(_bg())

    async def _extract_embedding(self, anomaly: AnomalyRecord) -> None:
        """为单条 anomaly 提取 embedding 向量并存储。"""
        from io import BytesIO

        import numpy as np
        from PIL import Image

        crop_path = anomaly.crop_path
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

        from app.repositories.embedding.repository import EmbeddingRepository
        from app.models.embedding import EmbeddingVector

        embedding_repo = EmbeddingRepository(self._session)
        existing_emb = await embedding_repo.get_by_anomaly_id(anomaly.id)
        if existing_emb is not None:
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

    async def _run_clustering(self) -> None:
        """收集所有 embedded 异常的向量，重新聚类。

        样本充足时用 UMAP+HDBSCAN 自动发现缺陷模式；
        样本不足时每个 anomaly 独立成 cluster，保证 VLM→review 流水线不中断。
        """
        import numpy as np

        from app.repositories.cluster.repository import ClusterMembershipRepository, ClusterRepository
        from app.repositories.embedding.repository import EmbeddingRepository

        embedding_repo = EmbeddingRepository(self._session)
        cluster_repo = ClusterRepository(self._session)
        membership_repo = ClusterMembershipRepository(self._session)

        all_embeddings = await embedding_repo.get_all_embeddings_with_ids()
        n_samples = len(all_embeddings)
        if n_samples == 0:
            return

        # 动态计算 HDBSCAN 最小簇大小
        if n_samples <= 10:
            min_cluster_size = 2
        elif n_samples <= 30:
            min_cluster_size = 3
        else:
            min_cluster_size = 5

        # 清理旧聚类数据（cluster + membership 一起清）
        old_clusters = await cluster_repo.list_all(offset=0, limit=10000)
        for old_c in old_clusters:
            old_members = await membership_repo.get_by_cluster(old_c.id)
            for m in old_members:
                await membership_repo.soft_delete(m.id)
            await cluster_repo.soft_delete(old_c.id)
        logger.info("pipeline_cleaned_old_clusters", count=len(old_clusters))

        embeddings_map: dict[str, np.ndarray] = {
            aid: np.array(vec, dtype=np.float32) for aid, vec in all_embeddings
        }
        ids = list(embeddings_map.keys())

        # ---- 样本不足：单例 cluster ----
        if n_samples < min_cluster_size:
            logger.info("pipeline_singleton_clustering", count=n_samples)
            for aid in ids:
                await self._create_singleton_cluster(
                    aid, cluster_repo, membership_repo
                )
            await self._session.commit()
            await self._trigger_vlm_for_pending(cluster_repo)
            return

        # ---- 正常聚类：UMAP + HDBSCAN ----
        if n_samples <= 10:
            min_samples, n_neighbors = 1, max(2, n_samples - 1)
        elif n_samples <= 30:
            min_samples, n_neighbors = 1, min(10, n_samples - 1)
        else:
            min_samples, n_neighbors = 2, min(15, n_samples - 1)

        try:
            from ml.clustering.pipeline import ClusteringPipeline
            pipeline_cls = ClusteringPipeline(
                umap_n_components=2,
                umap_n_neighbors=n_neighbors,
                umap_min_dist=0.1,
                hdbscan_min_cluster_size=min_cluster_size,
                hdbscan_min_samples=min_samples,
            )
            matrix = np.stack([embeddings_map[i] for i in ids])
            result = pipeline_cls.fit_predict(matrix, ids)

            labels = result["labels"]
            probabilities = result["probabilities"]
            umap_coords = result["umap_coords"]
            representatives = pipeline_cls.get_representatives(labels, probabilities, n_per_cluster=5)

            unique_labels = set(int(lb) for lb in labels)
            has_clusters = any(lb != -1 for lb in unique_labels)
            if not has_clusters:
                # 所有点被 HDBSCAN 判定为噪声 → 退化为单例 cluster
                noise_count = sum(1 for lb in labels if int(lb) == -1)
                logger.info("pipeline_clustering_all_noise_fallback", total=n_samples, noise=noise_count)
                for aid in ids:
                    await self._create_singleton_cluster(aid, cluster_repo, membership_repo)
                await self._session.commit()
                await self._trigger_vlm_for_pending(cluster_repo)
                return

            # 写入 HDBSCAN 聚类结果
            from app.models.cluster import Cluster, ClusterMembership
            for label in sorted(unique_labels):
                if label == -1:
                    continue
                label_indices = [i for i, lb in enumerate(labels) if int(lb) == label]
                rep_indices = representatives.get(label, [])
                rep_ids = [ids[i] for i in rep_indices] if rep_indices else []

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
            num_clusters = len([l for l in unique_labels if l != -1])
            logger.info("pipeline_clustering_done", num_clusters=num_clusters)
            await self._trigger_vlm_for_pending(cluster_repo)

        except Exception as e:
            logger.error("pipeline_clustering_failed", error=str(e))
            await self._session.rollback()

    async def _create_singleton_cluster(
        self,
        anomaly_id: str,
        cluster_repo,
        membership_repo,
    ) -> None:
        """为单条 anomaly 创建一个仅包含自身的 cluster。"""
        from app.models.cluster import Cluster, ClusterMembership

        cluster = Cluster(
            id=generate_uuid(),
            hdbscan_label=0,
            sample_count=1,
            representative_ids=json.dumps([anomaly_id]),
            centroid=None,
            umap_x=0.0,
            umap_y=0.0,
            hdbscan_probability=1.0,
            status="pending_review",
            clustering_run_at=datetime.now(tz=timezone.utc),
        )
        await cluster_repo.create(cluster)

        membership = ClusterMembership(
            id=generate_uuid(),
            cluster_id=cluster.id,
            anomaly_id=anomaly_id,
            membership_score=1.0,
        )
        await membership_repo.create(membership)
        await self._repo.update_status(anomaly_id, "clustered")
        logger.info("singleton_cluster_created", anomaly_id=anomaly_id, cluster_id=cluster.id)

    async def _trigger_vlm_for_pending(self, cluster_repo) -> None:
        """对状态为 pending_review 的 cluster 自动触发 VLM 分析。"""
        new_cluster_ids = [
            c.id for c in await cluster_repo.list_all(
                status="pending_review", offset=0, limit=100
            )
        ]
        if new_cluster_ids:
            logger.info("pipeline_auto_vlm", cluster_ids=new_cluster_ids)
            from app.api.deps import get_vlm_analyzer
            from app.services.multimodal.service import VLMService
            vlm = VLMService(self._session, get_vlm_analyzer(), self._minio)
            for cid in new_cluster_ids:
                try:
                    await vlm.analyze_cluster(cid)
                except Exception as e:
                    logger.warning("pipeline_auto_vlm_failed", cluster_id=cid, error=str(e))
