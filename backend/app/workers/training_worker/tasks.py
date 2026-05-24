from __future__ import annotations

import json
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
) -> tuple[list[np.ndarray], list[int]]:
    async with async_session_factory() as session:
        cluster_repo = ClusterRepository(session)
        membership_repo = ClusterMembershipRepository(session)
        reviewed_clusters = await cluster_repo.get_by_status("reviewed", offset=0, limit=10000)

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
) -> dict[str, object]:
    if class_names is None:
        class_names = ["false_alarm", "real_defect"]

    logger.info(
        "training_started",
        model_type=model_type,
        epochs=epochs,
        batch_size=batch_size,
    )

    import mlflow

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment("filter_classifier")

    mlflow_run_id: str | None = None

    try:
        images, labels = run_async(_load_training_data(anomaly_ids or []))

        if len(images) < 4:
            logger.warning("training_insufficient_data", count=len(images))
            return {"status": "failed", "error": f"Insufficient training data: {len(images)} images"}

        from sklearn.model_selection import train_test_split

        train_imgs, val_imgs, train_lbls, val_lbls = train_test_split(
            images, labels, test_size=validation_split, stratify=labels, random_state=42,
        )

        from torchvision import transforms as T

        transform = T.Compose([
            T.Resize((224, 224)),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

        train_ds = _ImageDataset(train_imgs, train_lbls, transform)
        val_ds = _ImageDataset(val_imgs, val_lbls, transform)

        output_dir = settings.model_dir / f"training_{generate_uuid()[:8]}"
        output_dir.mkdir(parents=True, exist_ok=True)

        from ml.classifier.trainer import FilterClassifierTrainer

        trainer = FilterClassifierTrainer(
            model_type=model_type,
            num_classes=num_classes,
            device="cpu",
            learning_rate=learning_rate,
        )

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
            })

            metrics = trainer.train(
                train_dataset=train_ds,
                val_dataset=val_ds,
                batch_size=batch_size,
                epochs=epochs,
                class_names=class_names,
                output_dir=output_dir,
            )

            numeric_metrics = {
                k: v for k, v in metrics.items() if isinstance(v, (float, int))
            }
            mlflow.log_metrics(numeric_metrics)

            torchscript_path = output_dir / "model.pt"
            trainer.export_torchscript(torchscript_path)

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
            artifact_path=str(torchscript_path),
            metrics=numeric_metrics,
            mlflow_run_id=mlflow_run_id,
        ))

        # 训练完成后自动部署到默认目标
        if settings.deploy_on_train_complete:
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


@celery_app.task(name="training.export_model")
def export_model(
    model_path: str,
    export_format: str = "torchscript",
) -> dict[str, object]:
    logger.info("export_started", model_path=model_path, format=export_format)
    try:
        from ml.classifier.trainer import FilterClassifierTrainer

        trainer = FilterClassifierTrainer(model_type="resnet18", device="cpu")
        trainer.load_checkpoint(model_path)

        output_path = Path(model_path).with_suffix(f".{export_format}")
        if export_format == "torchscript":
            trainer.export_torchscript(output_path)
        elif export_format == "onnx":
            trainer.export_onnx(output_path)
        else:
            return {"status": "failed", "error": f"Unsupported format: {export_format}"}

        logger.info("export_complete", output_path=str(output_path))
        return {"status": "completed", "export_format": export_format, "artifact_path": str(output_path)}
    except Exception as e:
        logger.error("export_failed", error=str(e))
        return {"status": "failed", "error": str(e)}
