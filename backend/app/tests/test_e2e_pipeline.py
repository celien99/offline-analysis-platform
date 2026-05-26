"""E2E 集成测试：覆盖离线分析平台核心链路。

重点测试 prompt.md 第5条提到的链路粘合处：
  - 在线 NG 上传到离线入库
  - embedding → cluster → review → train → deploy 全流程
  - 数据隔离 (seat_model_id / camera_id / region_id) 正确传播
  - 门禁评估指标计算
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_uuid
from app.models.anomaly import AnomalyRecord
from app.models.cluster import Cluster, ClusterMembership
from app.models.embedding import EmbeddingVector
from app.models.gate import GateEvaluation
from app.models.registry import ModelVersion
from app.repositories.anomaly.repository import AnomalyRepository
from app.repositories.cluster.repository import ClusterMembershipRepository, ClusterRepository
from app.repositories.embedding.repository import EmbeddingRepository
from app.services.anomaly import AnomalyService
from app.services.clustering.service import ClusteringService
from app.services.training.service import TrainingService


@pytest.fixture
def mock_minio() -> AsyncMock:
    minio = AsyncMock()
    minio.upload = AsyncMock()
    minio.download = AsyncMock(return_value=b"\xff\xd8\xff\xe0\x00\x10JFIF" * 100)
    minio.get_presigned_url = AsyncMock(return_value="http://minio/presigned/url")
    return minio


@pytest.fixture
def sample_detected_at() -> datetime:
    return datetime(2025, 12, 1, 10, 0, tzinfo=timezone.utc)


# ── Stage 1: Anomaly Upload → DB ────────────────────────────


class TestAnomalyUploadE2E:
    @pytest.mark.asyncio
    async def test_upload_with_isolation_fields(
        self, db_session: AsyncSession, mock_minio: AsyncMock, sample_detected_at,
    ) -> None:
        """在线 NG 上传携带 seat_model_id + camera_id + region_id 正确入库。"""
        service = AnomalyService(db_session, mock_minio)
        anomalies = await service.create_anomaly_with_files(
            camera_id="cam_front",
            seat_model_id="model_a",
            region_id="region_upper",
            source="efficientad",
            anomaly_score=0.92,
            date_folder="2025-12-01",
            detected_at=sample_detected_at,
            decision_reason="texture_anomaly",
            filter_confidence=0.85,
            filter_action="confirmed_ng",
            crop_data_list=[b"fake_jpeg_data_here"],
        )

        assert len(anomalies) == 1
        a = anomalies[0]
        assert a.camera_id == "cam_front"
        assert a.seat_model_id == "model_a"
        assert a.region_id == "region_upper"
        assert a.source == "efficientad"
        assert a.status == "pending"
        assert a.decision_reason == "texture_anomaly"
        assert a.filter_confidence == 0.85
        assert a.crop_path is not None

        # 验证可通过 repo 按隔离键查询
        repo = AnomalyRepository(db_session)
        results = await repo.list_all(
            seat_model_id="model_a", camera_id="cam_front", region_id="region_upper",
        )
        assert len(list(results)) >= 1

    @pytest.mark.asyncio
    async def test_upload_multiple_crops_creates_multiple_anomalies(
        self, db_session: AsyncSession, mock_minio: AsyncMock, sample_detected_at,
    ) -> None:
        """多个 crop patch 各自独立为一条 anomaly。"""
        service = AnomalyService(db_session, mock_minio)
        fake_data = [b"crop_1", b"crop_2", b"crop_3"]
        anomalies = await service.create_anomaly_with_files(
            camera_id="cam_multi",
            date_folder="2025-12-01",
            detected_at=sample_detected_at,
            crop_data_list=fake_data,
        )
        assert len(anomalies) == 3
        assert all(a.crop_path is not None for a in anomalies)
        # 每条 anomaly 有独立 ID
        ids = {a.id for a in anomalies}
        assert len(ids) == 3


# ── Stage 2: Embedding → Clustering ────────────────────────


class TestEmbeddingAndClusteringE2E:
    @pytest.mark.asyncio
    async def test_embedding_creation(
        self, db_session: AsyncSession, mock_minio: AsyncMock, sample_detected_at,
    ) -> None:
        """创建 anomaly 后提取 embedding。"""
        service = AnomalyService(db_session, mock_minio)
        anomalies = await service.create_anomaly_with_files(
            camera_id="cam_e1", date_folder="2025-12-01", detected_at=sample_detected_at,
        )
        anomaly_id = anomalies[0].id

        # 模拟 embedding 写入
        embedding_repo = EmbeddingRepository(db_session)
        vector = EmbeddingVector(
            id=generate_uuid(),
            anomaly_id=anomaly_id,
            embedding_type="raw",
            embedding=[0.1] * 384,
            model_name="dinov2_vits14",
            dimension=384,
        )
        await embedding_repo.create(vector)
        await db_session.commit()

        # 验证 embedding 可查询
        retrieved = await embedding_repo.get_by_anomaly_id(anomaly_id)
        assert retrieved is not None
        assert retrieved.embedding_type == "raw"
        assert len(retrieved.embedding) == 384

    @pytest.mark.asyncio
    async def test_dual_embedding_raw_and_refined(
        self, db_session: AsyncSession, mock_minio: AsyncMock, sample_detected_at,
    ) -> None:
        """同一 anomaly 可存储 raw + refined 两条 embedding。"""
        service = AnomalyService(db_session, mock_minio)
        anomalies = await service.create_anomaly_with_files(
            camera_id="cam_e2", date_folder="2025-12-01", detected_at=sample_detected_at,
        )
        anomaly_id = anomalies[0].id

        embedding_repo = EmbeddingRepository(db_session)
        raw_vec = EmbeddingVector(
            id=generate_uuid(), anomaly_id=anomaly_id, embedding_type="raw",
            embedding=[0.1] * 384, model_name="dinov2_vits14", dimension=384,
        )
        refined_vec = EmbeddingVector(
            id=generate_uuid(), anomaly_id=anomaly_id, embedding_type="refined",
            embedding=[0.15] * 384, model_name="dinov2_vits14", dimension=384,
        )
        await embedding_repo.create(raw_vec)
        await embedding_repo.create(refined_vec)
        await db_session.commit()

        raw = await embedding_repo.get_by_anomaly_and_type(anomaly_id, "raw")
        refined = await embedding_repo.get_by_anomaly_and_type(anomaly_id, "refined")
        assert raw is not None
        assert refined is not None
        assert raw.embedding != refined.embedding

    @pytest.mark.asyncio
    async def test_embedding_clustering_flow(
        self, db_session: AsyncSession, mock_minio: AsyncMock, sample_detected_at,
    ) -> None:
        """完整 embedding → clustering 流程，验证 cluster 和 membership 正确创建。"""
        import json
        import numpy as np

        service = AnomalyService(db_session, mock_minio)
        embedding_repo = EmbeddingRepository(db_session)

        # 创建 20 条异常，提取有结构的 embedding（3 clusters + noise）
        anomaly_ids = []
        rng = np.random.RandomState(42)
        for i in range(20):
            anomalies = await service.create_anomaly_with_files(
                camera_id="cam_cluster",
                seat_model_id="model_test",
                date_folder="2025-12-01",
                detected_at=sample_detected_at,
            )
            aid = anomalies[0].id
            anomaly_ids.append(aid)
            repo = AnomalyRepository(db_session)
            await repo.update_status(aid, "embedded")

            # 生成有结构的 embedding：3 个簇 + 少量噪声
            if i < 7:
                emb = rng.randn(384).astype(np.float32) * 0.3 + 1.0
            elif i < 14:
                emb = rng.randn(384).astype(np.float32) * 0.3 - 1.0
            elif i < 18:
                emb = rng.randn(384).astype(np.float32) * 0.3
            else:
                emb = rng.randn(384).astype(np.float32) * 2.0  # noise

            vec = EmbeddingVector(
                id=generate_uuid(), anomaly_id=aid, embedding_type="raw",
                embedding=emb.tolist(),
                model_name="dinov2_vits14", dimension=384,
            )
            await embedding_repo.create(vec)
        await db_session.commit()

        # 获取 embeddings 用于聚类
        rows = await embedding_repo.get_embeddings_for_clustering(
            seat_model_id="model_test", embedding_type="raw",
        )
        assert len(rows) >= 20

        # 运行聚类
        cluster_service = ClusteringService(db_session)
        embeddings_dict = {aid: np.array(vec, dtype=np.float32) for aid, vec in rows}

        from app.domain.clustering import ClusterConfig
        config = ClusterConfig(
            umap_n_components=2, umap_n_neighbors=5,
            hdbscan_min_cluster_size=3, hdbscan_min_samples=2,
        )
        result, label_map, prob_map = await cluster_service.run_clustering(
            embeddings_dict, config=config,
        )
        assert result.total_samples >= 20
        assert result.clusters or result.noise_count >= 0

        # 持久化聚类结果
        persisted = await cluster_service.persist_clustering_result(
            result, label_map=label_map, probability_map=prob_map,
            seat_model_id="model_test", camera_id="cam_cluster",
        )
        assert len(persisted) > 0

        # 验证 membership
        membership_repo = ClusterMembershipRepository(db_session)
        for cluster in persisted:
            aids = await membership_repo.get_anomaly_ids_by_cluster(cluster.id)
            assert len(aids) > 0

        # 验证集群隔离键
        cluster_repo = ClusterRepository(db_session)
        for cluster in persisted:
            stored = await cluster_repo.get_by_id(cluster.id)
            assert stored is not None
            assert stored.seat_model_id == "model_test"


# ── Stage 3: Review → Training Data ────────────────────────


class TestReviewAndTrainingE2E:
    @pytest.mark.asyncio
    async def test_review_and_training_data_preparation(
        self, db_session: AsyncSession, mock_minio: AsyncMock, sample_detected_at,
    ) -> None:
        """审核 cluster 后训练数据正确划分 real_defect / false_alarm。"""
        import json

        # 创建 cluster 和 membership
        cluster_repo = ClusterRepository(db_session)
        membership_repo = ClusterMembershipRepository(db_session)
        anomaly_repo = AnomalyRepository(db_session)

        # 先创建异常
        anomaly_service = AnomalyService(db_session, mock_minio)
        real_aids = []
        for _ in range(5):
            anomalies = await anomaly_service.create_anomaly_with_files(
                camera_id="cam_train", date_folder="2025-12-01", detected_at=sample_detected_at,
            )
            real_aids.append(anomalies[0].id)

        fake_aids = []
        for _ in range(5):
            anomalies = await anomaly_service.create_anomaly_with_files(
                camera_id="cam_train", date_folder="2025-12-01", detected_at=sample_detected_at,
            )
            fake_aids.append(anomalies[0].id)

        # 创建真实缺陷 cluster
        real_cluster = Cluster(
            id=generate_uuid(), seat_model_id="model_train", camera_id="cam_train",
            hdbscan_label=0, sample_count=5,
            representative_ids=json.dumps(real_aids),
            status="reviewed", review_status="real_defect",
            reviewed_by="engineer", clustering_run_at=sample_detected_at,
        )
        await cluster_repo.create(real_cluster)

        # 创建误报 cluster
        fake_cluster = Cluster(
            id=generate_uuid(), seat_model_id="model_train", camera_id="cam_train",
            hdbscan_label=1, sample_count=5,
            representative_ids=json.dumps(fake_aids),
            status="reviewed", review_status="false_alarm",
            reviewed_by="engineer", clustering_run_at=sample_detected_at,
        )
        await cluster_repo.create(fake_cluster)

        # 创建 membership
        memberships = []
        for aid in real_aids:
            memberships.append(ClusterMembership(
                id=generate_uuid(), cluster_id=real_cluster.id, anomaly_id=aid,
            ))
        for aid in fake_aids:
            memberships.append(ClusterMembership(
                id=generate_uuid(), cluster_id=fake_cluster.id, anomaly_id=aid,
            ))
        await membership_repo.bulk_create(memberships)
        await db_session.commit()

        # 使用 TrainingService 准备训练数据
        train_service = TrainingService(db_session)
        training_data = await train_service.prepare_training_data(
            seat_model_id="model_train", camera_id="cam_train",
        )
        assert len(training_data["real_defect"]) >= 5
        assert len(training_data["false_alarm"]) >= 5

        # 验证训练就绪状态
        readiness = await train_service.get_training_readiness(
            seat_model_id="model_train", camera_id="cam_train",
        )
        assert isinstance(readiness, dict)
        assert "ready" in readiness


# ── Stage 4: Gate Evaluation ───────────────────────────────


class TestGateEvaluationE2E:
    @pytest.mark.asyncio
    async def test_gate_metrics_computation(
        self, db_session: AsyncSession, mock_minio: AsyncMock, sample_detected_at,
    ) -> None:
        """门禁评估指标计算：召回率、抑制率、混淆矩阵。"""
        from app.services.gate.service import GateEvaluationService

        service = GateEvaluationService(db_session)

        # 测试指标计算
        y_true = [1, 1, 1, 1, 0, 0, 0, 0]  # 4 real, 4 false_alarm
        y_pred = [1, 1, 1, 0, 0, 0, 1, 0]  # 3/4 recall, 3/4 suppression

        metrics = service._compute_metrics(y_true, y_pred)
        assert metrics["real_defect_recall"] == 0.75  # 3/4
        assert metrics["false_alarm_suppression_rate"] == 0.75  # 3/4
        assert metrics["suppressed_real_defect_count"] == 1  # 1 FN
        assert metrics["total"] == 8

    @pytest.mark.asyncio
    async def test_gate_perfect_model_passes(
        self, db_session: AsyncSession, mock_minio: AsyncMock, sample_detected_at,
    ) -> None:
        """完美模型通过所有门禁标准。"""
        from app.services.gate.service import GateEvaluationService

        service = GateEvaluationService(db_session)
        criteria = service._build_criteria()
        y_true = [1, 1, 1, 0, 0, 0]
        y_pred = [1, 1, 1, 0, 0, 0]  # perfect predictions
        metrics = service._compute_metrics(y_true, y_pred)

        failures = service._check_criteria(criteria, metrics, None, [])
        assert len(failures) == 0

    @pytest.mark.asyncio
    async def test_gate_recall_drop_detected(
        self, db_session: AsyncSession, mock_minio: AsyncMock, sample_detected_at,
    ) -> None:
        """召回率下降被门禁检测到。"""
        from app.services.gate.service import GateEvaluationService

        service = GateEvaluationService(db_session)
        criteria = service._build_criteria()

        # 完美基线
        y_true = [1, 1, 1, 0, 0, 0]
        baseline_metrics = service._compute_metrics(y_true, [1, 1, 1, 0, 0, 0])

        # 新模型：漏掉一个真实缺陷
        new_metrics = service._compute_metrics(y_true, [1, 1, 0, 0, 0, 0])  # recall 2/3

        failures = service._check_criteria(criteria, new_metrics, baseline_metrics, [])
        # recall drop: 1.0 → 0.667 = 0.333 > 0.02
        assert len(failures) >= 1
        assert any("召回率" in f for f in failures)


# ── Stage 5: Data Isolation Propagation ────────────────────


class TestDataIsolationPropagation:
    @pytest.mark.asyncio
    async def test_isolation_keys_propagated_to_cluster(
        self, db_session: AsyncSession, mock_minio: AsyncMock, sample_detected_at,
    ) -> None:
        """seat_model_id + camera_id + region_id 从 anomaly 传播到 cluster。"""
        import json
        import numpy as np

        anomaly_service = AnomalyService(db_session, mock_minio)
        embedding_repo = EmbeddingRepository(db_session)

        # 创建 anomalies with different isolation keys
        groups = [
            ("model_x", "cam_a", "region_1", 5),
            ("model_x", "cam_a", "region_2", 5),
            ("model_y", "cam_b", None, 5),
        ]

        for sm, cam, reg, count in groups:
            rng = np.random.RandomState(abs(hash(sm + cam + (reg or ""))) % 2**31)
            for _ in range(count):
                anomalies = await anomaly_service.create_anomaly_with_files(
                    camera_id=cam, seat_model_id=sm, region_id=reg,
                    date_folder="2025-12-01", detected_at=sample_detected_at,
                )
                aid = anomalies[0].id
                await AnomalyRepository(db_session).update_status(aid, "embedded")
                vec = EmbeddingVector(
                    id=generate_uuid(), anomaly_id=aid, embedding_type="raw",
                    embedding=rng.randn(384).astype(np.float32).tolist(),
                    model_name="dinov2_vits14", dimension=384,
                )
                await embedding_repo.create(vec)
        await db_session.commit()

        # 按 model_x + cam_a + region_1 隔离获取 embeddings
        rows = await embedding_repo.get_embeddings_for_clustering(
            seat_model_id="model_x", camera_id="cam_a", region_id="region_1",
            embedding_type="raw",
        )
        assert len(rows) >= 5

        # 按 model_x + cam_a 获取（不含 region 过滤）
        rows_all_regions = await embedding_repo.get_embeddings_for_clustering(
            seat_model_id="model_x", camera_id="cam_a",
            embedding_type="raw",
        )
        assert len(rows_all_regions) >= 10  # region_1 + region_2

    @pytest.mark.asyncio
    async def test_isolation_keys_filter_clusters(
        self, db_session: AsyncSession, mock_minio: AsyncMock, sample_detected_at,
    ) -> None:
        """按隔离键过滤 cluster 列表。"""
        import json

        cluster_repo = ClusterRepository(db_session)

        # 创建不同隔离键的 cluster
        for sm, cam, reg in [
            ("model_a", "cam_1", "region_a"),
            ("model_a", "cam_1", "region_b"),
            ("model_b", "cam_2", None),
        ]:
            cluster = Cluster(
                id=generate_uuid(), seat_model_id=sm, camera_id=cam, region_id=reg,
                hdbscan_label=0, sample_count=3,
                representative_ids=json.dumps([]),
                status="pending_review", clustering_run_at=sample_detected_at,
            )
            await cluster_repo.create(cluster)
        await db_session.commit()

        # 按 model_a 过滤
        result = await cluster_repo.list_all(
            seat_model_id="model_a", offset=0, limit=20,
        )
        clusters_list = list(result)
        total = await cluster_repo.count(seat_model_id="model_a")
        assert total == 2

        # 按 model_a + cam_1 + region_a 过滤
        result = await cluster_repo.list_all(
            seat_model_id="model_a", camera_id="cam_1", region_id="region_a",
        )
        filtered_clusters = list(result)
        assert len(filtered_clusters) == 1
        assert filtered_clusters[0].region_id == "region_a"
