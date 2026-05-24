from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.common.logging import get_logger
from app.schemas.common import StatusResponse
from app.schemas.training import TrainingStartRequest, TrainingStatusResponse
from app.services.training.service import TrainingService
from app.workers.training_worker.fastflow_task import train_fastflow as train_fastflow_task
from app.workers.training_worker.tasks import train_filter_classifier

router = APIRouter(prefix="/api/training", tags=["training"])
logger = get_logger(__name__)


@router.post("/start", response_model=StatusResponse)
async def start_training(
    request: TrainingStartRequest,
) -> StatusResponse:
    task = train_filter_classifier.delay(
        model_type=request.model_type,
        num_classes=request.num_classes,
        batch_size=request.batch_size,
        epochs=request.epochs,
        learning_rate=request.learning_rate,
        validation_split=request.validation_split,
        class_names=request.class_names,
        augmentations=request.augmentations,
        anomaly_ids=request.anomaly_ids,
    )
    logger.info(
        "training_started",
        task_id=task.id,
        model_type=request.model_type,
    )
    return StatusResponse(
        status="queued",
        message=f"Training task {task.id} dispatched",
    )


@router.post("/fastflow/start", response_model=StatusResponse)
async def start_fastflow_training(
    good_images_dir: str = Query(..., description="正常图像目录路径"),
    backbone: str = Query(default="resnet18", pattern=r"^(resnet18|wide_resnet50_2)$"),
    flow_steps: int = Query(default=8, ge=2, le=16),
    batch_size: int = Query(default=8, ge=1, le=32),
    epochs: int = Query(default=50, ge=5, le=200),
    learning_rate: float = Query(default=1e-3, ge=1e-5, le=1e-1),
    freeze_backbone: bool = Query(default=True),
) -> StatusResponse:
    """启动 FastFlow 端到端异常检测模型训练。

    FastFlow 学习正常图像的 2D Normalizing Flow 分布，
    推理时偏离训练分布的图像被判定为异常。
    输入参数 good_images_dir 为正常（无缺陷）图像所在目录。
    """
    from pathlib import Path

    img_dir = Path(good_images_dir)
    if not img_dir.is_dir():
        return StatusResponse(
            status="failed",
            message=f"目录不存在: {good_images_dir}",
        )

    exts = ("*.jpg", "*.jpeg", "*.png", "*.bmp")
    image_paths = []
    for ext in exts:
        image_paths.extend(str(p) for p in img_dir.glob(ext))

    if len(image_paths) < 4:
        return StatusResponse(
            status="failed",
            message=f"需要至少 4 张图像，目录中有 {len(image_paths)} 张",
        )

    task = train_fastflow_task.delay(
        good_image_paths=image_paths,
        backbone=backbone,
        flow_steps=flow_steps,
        batch_size=batch_size,
        epochs=epochs,
        learning_rate=learning_rate,
        freeze_backbone=freeze_backbone,
    )
    logger.info(
        "fastflow_training_dispatched",
        task_id=task.id,
        backbone=backbone,
        image_count=len(image_paths),
    )
    return StatusResponse(
        status="queued",
        message=f"FastFlow training task {task.id} dispatched with {len(image_paths)} images",
    )


@router.get("/status/{task_id}", response_model=TrainingStatusResponse)
async def get_training_status(
    task_id: str,
) -> TrainingStatusResponse:
    from celery.result import AsyncResult
    from app.infrastructure.queue.celery_app import celery_app

    result = AsyncResult(task_id, app=celery_app)

    return TrainingStatusResponse(
        task_id=task_id,
        status=result.state.lower(),
        error_message=str(result.info.get("error")) if result.failed() else None,
    )


@router.get(
    "/models",
    response_model=dict,
)
async def list_trained_models(
    model_type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> dict:
    service = TrainingService(session)
    offset = (page - 1) * page_size
    models, total = await service.list_models(
        model_type=model_type,
        offset=offset,
        limit=page_size,
    )
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "models": [
            {
                "model_id": m.id,
                "model_name": m.model_name,
                "version": m.version,
                "model_type": m.model_type,
                "framework": m.framework,
                "status": m.status,
                "trained_at": m.trained_at.isoformat() if m.trained_at else None,
            }
            for m in models
        ],
    }
