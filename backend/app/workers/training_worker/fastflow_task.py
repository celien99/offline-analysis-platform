"""FastFlow 训练 Celery task — 在正常图像上训练端到端异常检测模型。"""

from __future__ import annotations

from pathlib import Path

from app.common.logging import get_logger
from app.core.config import settings
from app.core.security import generate_uuid
from app.infrastructure.database.session import async_session_factory
from app.infrastructure.queue.celery_app import celery_app
from app.models.registry import ModelVersion
from app.workers import run_async

logger = get_logger(__name__)


@celery_app.task(name="training.train_fastflow")
def train_fastflow(
    good_image_paths: list[str],
    *,
    backbone: str = "resnet18",
    flow_steps: int = 8,
    batch_size: int = 8,
    epochs: int = 50,
    learning_rate: float = 1e-3,
    validation_split: float = 0.1,
    freeze_backbone: bool = True,
    input_size: tuple[int, int] = (256, 256),
) -> dict[str, object]:
    """在正常图像上训练 FastFlow 模型。

    Args:
        good_image_paths: 正常（无缺陷）参考图像文件路径列表
        backbone: 特征提取 backbone (resnet18 | wide_resnet50_2)
        flow_steps: 每个尺度的 coupling layer 数量
        batch_size: 批大小
        epochs: 最大训练轮数
        learning_rate: 学习率
        validation_split: 验证集比例
        freeze_backbone: 是否冻结 backbone 权重
        input_size: 输入图像尺寸 (H, W)
    """
    logger.info(
        "fastflow_training_started",
        backbone=backbone,
        epochs=epochs,
        image_count=len(good_image_paths),
    )

    try:
        if len(good_image_paths) < 4:
            return {"status": "failed", "error": f"Need >= 4 images, got {len(good_image_paths)}"}

        from ml.anomaly_detection.fastflow import FastFlowConfig
        from ml.anomaly_detection.trainer import FastFlowTrainer
        import mlflow

        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        mlflow.set_experiment("fastflow")

        config = FastFlowConfig(
            backbone=backbone,
            flow_steps=flow_steps,
            input_size=input_size,
        )

        output_dir = settings.model_dir / f"fastflow_{generate_uuid()[:8]}"
        output_dir.mkdir(parents=True, exist_ok=True)

        trainer = FastFlowTrainer(
            config=config,
            device="cpu",
            learning_rate=learning_rate,
        )

        with mlflow.start_run() as run:
            mlflow.log_params({
                "backbone": backbone,
                "flow_steps": flow_steps,
                "batch_size": batch_size,
                "epochs": epochs,
                "learning_rate": learning_rate,
                "freeze_backbone": freeze_backbone,
                "train_images": len(good_image_paths),
            })

            metrics = trainer.train(
                image_paths=good_image_paths,
                batch_size=batch_size,
                epochs=epochs,
                validation_split=validation_split,
                output_dir=output_dir,
                freeze_backbone=freeze_backbone,
            )

            if "error" in metrics:
                return metrics

            numeric_metrics = {
                k: v for k, v in metrics.items() if isinstance(v, (float, int))
            }
            mlflow.log_metrics(numeric_metrics)

            # 导出 TorchScript
            torchscript_path = output_dir / "model.pt"
            trainer.export_torchscript(torchscript_path)

            mlflow.log_artifact(str(torchscript_path), artifact_path="model")

        model_version = run_async(_create_fastflow_model_version(
            model_name=f"fastflow_{backbone}",
            backbone=backbone,
            artifact_path=str(torchscript_path),
            metrics=numeric_metrics,
            mlflow_run_id=run.info.run_id,
        ))

        logger.info(
            "fastflow_training_complete",
            backbone=backbone,
            metrics=numeric_metrics,
            mlflow_run_id=run.info.run_id,
        )

        return {
            "status": "completed",
            "backbone": backbone,
            "artifact_path": str(torchscript_path),
            "metrics": numeric_metrics,
            "mlflow_run_id": run.info.run_id,
            "model_version_id": model_version.id,
            "model_version": model_version.version,
        }

    except Exception as e:
        logger.error("fastflow_training_failed", error=str(e))
        return {"status": "failed", "error": str(e)}


async def _create_fastflow_model_version(
    model_name: str,
    backbone: str,
    artifact_path: str,
    metrics: dict[str, float],
    mlflow_run_id: str | None = None,
) -> ModelVersion:
    """在数据库中创建 FastFlow 的 model_version 记录。"""
    import json
    from datetime import datetime, timezone

    from app.repositories.registry.model_version import ModelVersionRepository

    async with async_session_factory() as session:
        model = ModelVersion(
            id=generate_uuid(),
            model_name=model_name,
            version=datetime.now(tz=timezone.utc).strftime("%Y%m%d%H%M%S"),
            model_type=f"fastflow_{backbone}",
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
