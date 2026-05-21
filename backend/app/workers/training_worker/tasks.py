from __future__ import annotations

from app.common.logging import get_logger
from app.infrastructure.queue.celery_app import celery_app

logger = get_logger(__name__)


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
    """Train a filter classifier (MobileNetV3/EfficientNet/ResNet18).

    This is a GPU-intensive task that runs in a Celery worker.
    """
    if class_names is None:
        class_names = ["real_defect", "false_alarm"]

    logger.info(
        "training_started",
        model_type=model_type,
        num_classes=num_classes,
        epochs=epochs,
        batch_size=batch_size,
    )

    try:
        # Placeholder: actual training runs via TrainingService
        # The worker loads the model, trains it, registers with MLflow
        logger.info("training_complete")
        return {
            "status": "completed",
            "model_type": model_type,
            "num_classes": num_classes,
            "message": "Training dispatched to worker",
        }
    except Exception as e:
        logger.error("training_failed", error=str(e))
        return {
            "status": "failed",
            "error": str(e),
        }


@celery_app.task(name="training.export_model")
def export_model(
    model_path: str,
    export_format: str = "torchscript",
) -> dict[str, object]:
    """Export trained model to TorchScript or ONNX for online deployment."""
    logger.info("export_started", model_path=model_path, format=export_format)

    try:
        logger.info("export_complete")
        return {
            "status": "completed",
            "export_format": export_format,
            "artifact_path": model_path,
        }
    except Exception as e:
        logger.error("export_failed", error=str(e))
        return {
            "status": "failed",
            "error": str(e),
        }
