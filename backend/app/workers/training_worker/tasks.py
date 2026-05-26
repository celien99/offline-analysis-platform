from __future__ import annotations

import json
from datetime import datetime
import os
from io import BytesIO
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset

from app.common.logging import get_logger
from app.core.config import settings
from app.core.security import generate_uuid
from app.infrastructure.database.session import async_session_factory
from app.infrastructure.queue.celery_app import celery_app
from app.infrastructure.storage.minio_client import minio_client
from app.models.registry import ModelVersion
from app.models.training import TrainingRun
from app.repositories.anomaly.repository import AnomalyRepository
from app.repositories.cluster.repository import ClusterMembershipRepository, ClusterRepository
from app.workers import run_async

logger = get_logger(__name__)


class _ImageDataset(Dataset):
    def __init__(
        self,
        images: list[np.ndarray],
        labels: list[int],
        transform: object,
    ) -> None:
        self._images = images
        self._labels = labels
        self._transform = transform

    def __len__(self) -> int:
        return len(self._images)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, int]:
        img = self._images[idx]
        pil = Image.fromarray(img.astype(np.uint8)).convert("RGB")
        tensor = self._transform(pil)
        return tensor, self._labels[idx]


async def _load_training_data(
    anomaly_ids: list[str],
    since: datetime | None = None,
    seat_model_id: str | None = None,
    camera_id: str | None = None,
    region_id: str | None = None,
) -> tuple[list[np.ndarray], list[int]]:
    """加载训练数据。since 不为 None 时仅加载该时间后审核的 cluster。支持隔离键过滤。"""
    async with async_session_factory() as session:
        cluster_repo = ClusterRepository(session)
        membership_repo = ClusterMembershipRepository(session)
        if since is not None:
            reviewed_clusters = await cluster_repo.get_reviewed_since(
                since, offset=0, limit=10000,
                seat_model_id=seat_model_id,
                camera_id=camera_id,
                region_id=region_id,
            )
        else:
            reviewed_clusters = await cluster_repo.get_by_status(
                "reviewed", offset=0, limit=10000,
                seat_model_id=seat_model_id,
                camera_id=camera_id,
                region_id=region_id,
            )

        image_label_pairs: list[tuple[str, int]] = []
        for cluster in reviewed_clusters:
            if cluster.review_status == "real_defect":
                label = 1
            elif cluster.review_status == "false_alarm":
                label = 0
            else:
                continue
            cluster_anomaly_ids = await membership_repo.get_anomaly_ids_by_cluster(cluster.id)
            for aid in cluster_anomaly_ids:
                if not anomaly_ids or aid in anomaly_ids:
                    image_label_pairs.append((aid, label))

    anomaly_repo_session = async_session_factory()
    async with anomaly_repo_session as session:
        anomaly_repo = AnomalyRepository(session)
        anomalies = await anomaly_repo.get_by_ids([aid for aid, _ in image_label_pairs])
        anomaly_map = {a.id: a for a in anomalies}

    images: list[np.ndarray] = []
    labels: list[int] = []
    for aid, label in image_label_pairs:
        anomaly = anomaly_map.get(aid)
        if anomaly is None or anomaly.crop_path is None:
            continue
        try:
            raw = await minio_client.download(anomaly.crop_path)
            img = np.array(Image.open(BytesIO(raw)).convert("RGB"))
            images.append(img)
            labels.append(label)
        except Exception as e:
            logger.warning("training_image_load_failed", anomaly_id=aid, error=str(e))

    return images, labels


@celery_app.task(name="training.train_filter_classifier")
def train_filter_classifier(
    model_type: str = "mobilenet_v3_small",
    num_classes: int = 2,
    batch_size: int = 32,
    epochs: int = 50,
    learning_rate: float = 0.001,
    validation_split: float = 0.2,
    class_names: list[str] | None = None,
    augmentations: bool = True,
    anomaly_ids: list[str] | None = None,
    fine_tune: bool = False,
    trigger: str = "manual",
    seat_model_id: str | None = None,
    camera_id: str | None = None,
    region_id: str | None = None,
) -> dict[str, object]:
    if class_names is None:
        class_names = ["false_alarm", "real_defect"]

    if trigger not in ("manual", "auto_threshold"):
        trigger = "manual"

    logger.info(
        "training_started",
        model_type=model_type,
        epochs=epochs,
        batch_size=batch_size,
        fine_tune=fine_tune,
        trigger=trigger,
    )

    import mlflow

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment("filter_classifier")

    mlflow_run_id: str | None = None

    try:
        # 增量训练：查找最新 checkpoint 和数据截止时间
        checkpoint_path: str | None = None
        since: datetime | None = None

        if fine_tune:
            async def _resolve_fine_tune() -> tuple[str | None, datetime | None]:
                from app.repositories.registry.model_version import ModelVersionRepository
                from app.repositories.training.repository import TrainingRunRepository

                async with async_session_factory() as session:
                    model_repo = ModelVersionRepository(session)
                    prev = await model_repo.get_latest_by_model_name(
                        f"filter_classifier_{model_type}", status="deployed"
                    )
                    if prev is None:
                        prev = await model_repo.get_latest_by_model_name(
                            f"filter_classifier_{model_type}"
                        )
                    if prev is None:
                        return None, None

                    cp = prev.artifact_path if prev.artifact_path and Path(prev.artifact_path).exists() else None

                    training_run_repo = TrainingRunRepository(session)
                    latest_run = await training_run_repo.get_latest_train()
                    cutoff = latest_run.started_at if latest_run else None
                    return cp, cutoff

            checkpoint_path, since = run_async(_resolve_fine_tune())
            if checkpoint_path is None:
                logger.warning("fine_tune_no_checkpoint_found", model_type=model_type)
                fine_tune = False

        images, labels = run_async(_load_training_data(
            anomaly_ids or [], since=since,
            seat_model_id=seat_model_id,
            camera_id=camera_id,
            region_id=region_id,
        ))

        if len(images) < 4:
            logger.warning("training_insufficient_data", count=len(images))
            return {"status": "failed", "error": f"Insufficient training data: {len(images)} images"}

        from sklearn.model_selection import train_test_split

        # 当类别极端不平衡时 stratify 会失败，回退到非分层划分
        try:
            train_imgs, val_imgs, train_lbls, val_lbls = train_test_split(
                images, labels, test_size=validation_split, stratify=labels, random_state=42,
            )
        except ValueError:
            logger.warning("training_stratify_failed", count=len(images))
            train_imgs, val_imgs, train_lbls, val_lbls = train_test_split(
                images, labels, test_size=validation_split, random_state=42,
            )

        from torchvision import transforms as T

        transform = T.Compose([
            T.Resize((224, 224)),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

        from ml.classifier.dual_modal.dataset import DualModalDataset

        train_dataset = DualModalDataset(
            images=train_imgs, labels=train_lbls,
            image_size=448, augment=augmentations,
        )
        val_dataset = DualModalDataset(
            images=val_imgs, labels=val_lbls,
            image_size=448, augment=False,
        )

        output_dir = settings.model_dir / f"training_{generate_uuid()[:8]}"
        output_dir.mkdir(parents=True, exist_ok=True)

        from ml.classifier.dual_modal import DualModalTrainer, DualModalConfig

        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"
        config = DualModalConfig(
            num_classes=num_classes,
            image_size=448,
            learning_rate=learning_rate,
            image_branch_lr=learning_rate * 0.1,
            batch_size=batch_size,
            epochs=epochs,
            early_stopping_patience=10,
            class_names=class_names or ["false_alarm", "real_defect"],
            output_dir=output_dir,
        )
        trainer = DualModalTrainer(config=config, device=device)

        with mlflow.start_run() as run:
            mlflow_run_id = run.info.run_id
            mlflow.log_params({
                "model_type": model_type,
                "num_classes": num_classes,
                "batch_size": batch_size,
                "epochs": epochs,
                "learning_rate": learning_rate,
                "validation_split": validation_split,
                "augmentations": augmentations,
                "train_samples": len(train_imgs),
                "val_samples": len(val_imgs),
                "train_type": "fine_tune" if fine_tune else "full",
            })

            metrics = trainer.train(train_dataset, val_dataset, output_dir=output_dir)

            numeric_metrics = {
                k: v for k, v in metrics.items() if isinstance(v, (float, int))
            }
            mlflow.log_metrics(numeric_metrics)

            torchscript_path = trainer.export_torchscript(os.path.join(str(output_dir), "model.pt"))

            mlflow.log_artifact(str(torchscript_path), artifact_path="model")
            # 模型注册 API 在旧版 MLflow 中可能不可用，失败不阻塞训练
            try:
                mlflow.pytorch.log_model(
                    trainer._model,
                    artifact_path="pytorch_model",
                    registered_model_name=f"filter_classifier_{model_type}",
                )
            except Exception as mlflow_err:
                logger.warning("mlflow_log_model_failed", error=str(mlflow_err))

        model_version = run_async(_create_model_version(
            model_name=f"filter_classifier_{model_type}",
            model_type=model_type,
            artifact_path=str(Path(torchscript_path).resolve()),
            metrics=numeric_metrics,
            mlflow_run_id=mlflow_run_id,
        ))

        # 记录训练执行记录（支撑增量训练数据范围判定）
        run_async(_create_training_run(
            model_version_id=model_version.id,
            trigger=trigger,
            train_type="fine_tune" if fine_tune else "full",
            reviewed_cluster_count=0,  # TODO: 从 _load_training_data 传回实际值
            total_anomaly_count=len(images),
            new_anomaly_count=0 if not fine_tune else len(images),
            metrics_json=json.dumps(numeric_metrics),
            seat_model_id=seat_model_id,
            camera_id=camera_id,
            region_id=region_id,
        ))

        # 训练完成后触发门禁评估，通过后自动部署
        if settings.gate_enabled:
            from celery import chain
            from app.workers.gate_worker.tasks import evaluate_model_gate

            if settings.deploy_on_train_complete:
                # chain: gate → deploy (gate 失败则跳过 deploy)
                default_target = settings.default_deploy_target
                auto_strategy = settings.deploy_auto_strategy
                pipeline = chain(
                    evaluate_model_gate.s(
                        model_version_id=model_version.id,
                        triggered_by="system:auto_gate",
                    ),
                    celery_app.signature(
                        "deployment.deploy_model_version",
                        kwargs={
                            "model_name": model_version.model_name,
                            "version": model_version.version,
                            "target": default_target,
                            "deployed_by": "system:training_worker",
                            "strategy": auto_strategy,
                            "require_gate_pass": True,
                        },
                    ),
                )
                result = pipeline.delay()
                logger.info(
                    "gate_and_deploy_chain_dispatched",
                    chain_id=result.id,
                    model_version_id=model_version.id,
                )
            else:
                # 只跑门禁，不自动部署
                evaluate_model_gate.delay(
                    model_version_id=model_version.id,
                    triggered_by="system:auto_gate",
                )
                logger.info(
                    "gate_evaluation_triggered",
                    model_version_id=model_version.id,
                )
        elif settings.deploy_on_train_complete:
            from app.workers.deployment_worker.tasks import deploy_model_version_task

            default_target = settings.default_deploy_target
            try:
                deploy_model_version_task.delay(
                    model_name=model_version.model_name,
                    version=model_version.version,
                    target=default_target,
                    deployed_by="system:training_worker",
                )
                logger.info(
                    "auto_deploy_triggered",
                    model_name=model_version.model_name,
                    version=model_version.version,
                    target=default_target,
                )
            except Exception as deploy_err:
                logger.warning(
                    "auto_deploy_failed",
                    target=default_target,
                    error=str(deploy_err),
                )

        logger.info(
            "training_complete",
            model_type=model_type,
            metrics=metrics,
            mlflow_run_id=mlflow_run_id,
        )
        return {
            "status": "completed",
            "model_type": model_type,
            "artifact_path": str(torchscript_path),
            "metrics": numeric_metrics,
            "mlflow_run_id": mlflow_run_id,
            "model_version_id": model_version.id,
            "model_version": model_version.version,
        }
    except Exception as e:
        logger.error("training_failed", error=str(e))
        return {"status": "failed", "error": str(e)}


async def _create_model_version(
    model_name: str,
    model_type: str,
    artifact_path: str,
    metrics: dict[str, float],
    mlflow_run_id: str | None = None,
) -> ModelVersion:
    from datetime import datetime, timezone

    from app.repositories.registry.model_version import ModelVersionRepository

    async with async_session_factory() as session:
        model = ModelVersion(
            id=generate_uuid(),
            model_name=model_name,
            version=datetime.now(tz=timezone.utc).strftime("%Y%m%d%H%M%S"),
            model_type=model_type,
            framework="pytorch",
            artifact_path=artifact_path,
            metrics_json=json.dumps(metrics),
            mlflow_run_id=mlflow_run_id,
            trained_at=datetime.now(tz=timezone.utc),
            status="registered",
        )
        repo = ModelVersionRepository(session)
        await repo.create(model)
        await session.commit()
        return model


@celery_app.task(name="training.check_and_auto_train")
def check_and_auto_train() -> dict[str, object]:
    """周期性检查是否有足够的新审核标签，满足条件则自动触发训练。"""
    from app.core.config import settings

    if not settings.auto_train_enabled:
        return {"status": "skipped", "reason": "auto_train_disabled"}

    async def _check() -> dict[str, object]:
        async with async_session_factory() as session:
            from app.services.training.service import TrainingService

            service = TrainingService(session)
            readiness = await service.get_training_readiness()

        if not readiness["ready"]:
            logger.info(
                "auto_train_not_ready",
                new=readiness["new_reviewed_clusters_since_last_train"],
                total=readiness["total_reviewed_clusters"],
            )
            return {"status": "skipped", **readiness}

        task = train_filter_classifier.delay(
            model_type=settings.auto_train_model_type,
            batch_size=settings.auto_train_batch_size,
            epochs=settings.auto_train_epochs,
            trigger="auto_threshold",
        )
        logger.info("auto_train_dispatched", task_id=task.id)
        return {"status": "dispatched", "task_id": str(task.id), **readiness}

    return run_async(_check())


async def _create_training_run(
    *,
    model_version_id: str,
    trigger: str,
    train_type: str,
    reviewed_cluster_count: int,
    total_anomaly_count: int,
    new_anomaly_count: int,
    metrics_json: str | None = None,
    seat_model_id: str | None = None,
    camera_id: str | None = None,
    region_id: str | None = None,
) -> TrainingRun:
    from datetime import datetime, timezone

    from app.models.training import TrainingRun
    from app.repositories.training.repository import TrainingRunRepository

    async with async_session_factory() as session:
        run = TrainingRun(
            id=generate_uuid(),
            model_version_id=model_version_id,
            trigger=trigger,
            train_type=train_type,
            reviewed_cluster_count=reviewed_cluster_count,
            total_anomaly_count=total_anomaly_count,
            new_anomaly_count=new_anomaly_count,
            metrics_json=metrics_json,
            started_at=datetime.now(tz=timezone.utc),
            completed_at=datetime.now(tz=timezone.utc),
            seat_model_id=seat_model_id,
            camera_id=camera_id,
            region_id=region_id,
        )
        repo = TrainingRunRepository(session)
        await repo.create(run)
        await session.commit()
        return run


@celery_app.task(name="training.export_model")
def export_model(
    model_path: str,
    export_format: str = "torchscript",
) -> dict[str, object]:
    logger.info("export_started", model_path=model_path, format=export_format)
    try:
        from ml.classifier.dual_modal import DualModalTrainer

        trainer = DualModalTrainer(device="cpu")
        trainer.load_checkpoint(model_path)

        output_path = Path(model_path).with_suffix(f".{export_format}")
        if export_format == "torchscript":
            trainer.export_torchscript(output_path)
        elif export_format == "onnx":
            return {"status": "failed", "error": "ONNX export not yet supported for DualModalFilter"}
        else:
            return {"status": "failed", "error": f"Unsupported format: {export_format}"}

        logger.info("export_complete", output_path=str(output_path))
        return {"status": "completed", "export_format": export_format, "artifact_path": str(output_path)}
    except Exception as e:
        logger.error("export_failed", error=str(e))
        return {"status": "failed", "error": str(e)}


# ══════════════════════════════════════════════════════════════
# 度量学习训练 (Metric Learning)
# ══════════════════════════════════════════════════════════════


async def _load_metric_training_data(
    anomaly_ids: list[str] | None = None,
) -> tuple[list[np.ndarray], list[int], list[str]]:
    """加载度量学习训练数据 — 按 defect_type 分组标注。

    返回 (images, labels, class_names)，labels 为 0..N-1 的整数，
    每个整数对应一个 defect_type 类别。
    """
    async with async_session_factory() as session:
        cluster_repo = ClusterRepository(session)
        membership_repo = ClusterMembershipRepository(session)
        reviewed = await cluster_repo.get_by_status("reviewed", offset=0, limit=10000)

        # 收集所有 defect_type
        defect_type_set: set[str] = set()
        aid_type_pairs: list[tuple[str, str]] = []
        for cluster in reviewed:
            if cluster.review_status != "real_defect" or not cluster.defect_type:
                continue
            dt = cluster.defect_type.strip()
            cluster_aids = await membership_repo.get_anomaly_ids_by_cluster(cluster.id)
            for aid in cluster_aids:
                if anomaly_ids is None or aid in anomaly_ids:
                    aid_type_pairs.append((aid, dt))
                    defect_type_set.add(dt)

        class_names = sorted(defect_type_set)
        type_to_label = {dt: idx for idx, dt in enumerate(class_names)}

    anomaly_repo_session = async_session_factory()
    async with anomaly_repo_session as session:
        anomaly_repo = AnomalyRepository(session)
        anomalies = await anomaly_repo.get_by_ids([aid for aid, _ in aid_type_pairs])
        anomaly_map = {a.id: a for a in anomalies}

    images: list[np.ndarray] = []
    labels: list[int] = []
    for aid, defect_type in aid_type_pairs:
        anomaly = anomaly_map.get(aid)
        if anomaly is None or anomaly.crop_path is None:
            continue
        try:
            raw = await minio_client.download(anomaly.crop_path)
            img = np.array(Image.open(BytesIO(raw)).convert("RGB"))
            images.append(img)
            labels.append(type_to_label[defect_type])
        except Exception as e:
            logger.warning("metric_training_image_load_failed", anomaly_id=aid, error=str(e))

    return images, labels, class_names


@celery_app.task(name="training.train_metric_embedding")
def train_metric_embedding(
    backbone_type: str = "mobilenet_v3_small",
    embedding_size: int = 256,
    loss_type: str = "arcface",
    batch_size: int = 32,
    epochs: int = 50,
    learning_rate: float = 0.001,
    validation_split: float = 0.2,
    trigger: str = "manual",
    anomaly_ids: list[str] | None = None,
    seat_model_id: str | None = None,
    camera_id: str | None = None,
    region_id: str | None = None,
) -> dict[str, object]:
    """使用 ArcFace/Triplet 度量学习训练缺陷嵌入模型"""
    if loss_type not in ("arcface", "triplet"):
        return {"status": "failed", "error": f"Unsupported loss_type: {loss_type}"}

    logger.info(
        "metric_training_started",
        backbone_type=backbone_type,
        embedding_size=embedding_size,
        loss_type=loss_type,
        epochs=epochs,
    )

    import mlflow
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment("metric_embedding")

    try:
        images, labels, class_names = run_async(
            _load_metric_training_data(anomaly_ids)
        )

        if len(class_names) < 2:
            logger.warning(
                "metric_training_insufficient_classes",
                class_count=len(class_names),
            )
            return {
                "status": "failed",
                "error": f"Need at least 2 defect types, got {len(class_names)}: {class_names}",
            }

        if len(images) < 10:
            return {
                "status": "failed",
                "error": f"Insufficient data: {len(images)} images",
            }

        from sklearn.model_selection import train_test_split
        try:
            train_imgs, val_imgs, train_lbls, val_lbls = train_test_split(
                images, labels, test_size=validation_split, stratify=labels, random_state=42,
            )
        except ValueError:
            train_imgs, val_imgs, train_lbls, val_lbls = train_test_split(
                images, labels, test_size=validation_split, random_state=42,
            )

        from torchvision import transforms as T
        transform = T.Compose([
            T.Resize((224, 224)),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

        # 重用 _ImageDataset
        train_ds = _ImageDataset(train_imgs, train_lbls, transform)
        val_ds = _ImageDataset(val_imgs, val_lbls, transform)

        output_dir = settings.model_dir / f"metric_training_{generate_uuid()[:8]}"
        output_dir.mkdir(parents=True, exist_ok=True)

        from ml.classifier.metric_learning import MetricEmbeddingTrainer

        device = "cuda" if torch.cuda.is_available() else "cpu"
        trainer = MetricEmbeddingTrainer(
            backbone_type=backbone_type,
            embedding_size=embedding_size,
            device=device,
            learning_rate=learning_rate,
            loss_type=loss_type,
        )

        with mlflow.start_run() as run:
            mlflow_run_id = run.info.run_id
            mlflow.log_params({
                "backbone_type": backbone_type,
                "embedding_size": embedding_size,
                "loss_type": loss_type,
                "num_classes": len(class_names),
                "class_names": json.dumps(class_names),
                "batch_size": batch_size,
                "epochs": epochs,
                "learning_rate": learning_rate,
                "train_samples": len(train_imgs),
                "val_samples": len(val_imgs),
            })

            metrics = trainer.train_with_arcface(
                train_dataset=train_ds,
                val_dataset=val_ds,
                num_classes=len(class_names),
                batch_size=batch_size,
                epochs=epochs,
                output_dir=output_dir,
            )

            numeric_metrics = {
                k: v for k, v in metrics.items()
                if isinstance(v, (float, int))
            }
            mlflow.log_metrics(numeric_metrics)

            torchscript_path = output_dir / "metric_embedding.pt"
            mlflow.log_artifact(str(torchscript_path), artifact_path="model")

        model_name = f"metric_embedding_{backbone_type}"
        model_version = run_async(_create_model_version(
            model_name=model_name,
            model_type="metric_embedding",
            artifact_path=str(torchscript_path.resolve()),
            metrics=numeric_metrics,
            mlflow_run_id=mlflow_run_id,
        ))

        run_async(_create_training_run(
            model_version_id=model_version.id,
            trigger=trigger,
            train_type="metric_learning",
            reviewed_cluster_count=len(class_names),
            total_anomaly_count=len(images),
            new_anomaly_count=len(images),
            metrics_json=json.dumps({**numeric_metrics, "class_names": class_names}),
            seat_model_id=seat_model_id,
            camera_id=camera_id,
            region_id=region_id,
        ))

        # 自动部署
        if settings.deploy_on_train_complete:
            from app.workers.deployment_worker.tasks import deploy_model_version_task
            try:
                deploy_model_version_task.delay(
                    model_name=model_version.model_name,
                    version=model_version.version,
                    target=settings.default_deploy_target,
                    deployed_by="system:metric_training_worker",
                )
            except Exception as deploy_err:
                logger.warning("metric_auto_deploy_failed", error=str(deploy_err))

        logger.info(
            "metric_training_complete",
            backbone_type=backbone_type,
            loss_type=loss_type,
            class_count=len(class_names),
            metrics=numeric_metrics,
        )
        return {
            "status": "completed",
            "model_type": "metric_embedding",
            "backbone_type": backbone_type,
            "embedding_size": embedding_size,
            "loss_type": loss_type,
            "num_classes": len(class_names),
            "artifact_path": str(torchscript_path),
            "metrics": numeric_metrics,
            "mlflow_run_id": mlflow_run_id,
            "model_version_id": model_version.id,
            "model_version": model_version.version,
        }
    except Exception as e:
        logger.error("metric_training_failed", error=str(e))
        return {"status": "failed", "error": str(e)}
