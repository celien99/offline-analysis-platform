from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.common.logging import get_logger
from app.schemas.common import StatusResponse
from app.schemas.training import MetricTrainingStartRequest, TrainingStartRequest, TrainingStatusResponse
from app.services.training.service import TrainingService
from app.workers.training_worker.tasks import train_filter_classifier, train_metric_embedding

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
        seat_model_id=request.seat_model_id,
        camera_id=request.camera_id,
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


@router.post("/metric-learning/start", response_model=StatusResponse)
async def start_metric_training(
    request: MetricTrainingStartRequest,
) -> StatusResponse:
    task = train_metric_embedding.delay(
        backbone_type=request.backbone_type,
        embedding_size=request.embedding_size,
        loss_type=request.loss_type,
        batch_size=request.batch_size,
        epochs=request.epochs,
        learning_rate=request.learning_rate,
        validation_split=request.validation_split,
        anomaly_ids=request.anomaly_ids,
        seat_model_id=request.seat_model_id,
        camera_id=request.camera_id,
    )
    logger.info(
        "metric_training_dispatched",
        task_id=task.id,
        backbone_type=request.backbone_type,
        loss_type=request.loss_type,
    )
    return StatusResponse(
        status="queued",
        message=f"Metric learning task {task.id} dispatched",
    )


@router.get("/status/{task_id}", response_model=TrainingStatusResponse)
async def get_training_status(
    task_id: str,
) -> TrainingStatusResponse:
    from celery.result import AsyncResult
    from app.infrastructure.queue.celery_app import celery_app

    result = AsyncResult(task_id, app=celery_app)

    error_msg = None
    if result.failed():
        info = result.info
        if isinstance(info, dict):
            error_msg = str(info.get("error", "")) or None
        elif info:
            error_msg = str(info)
    return TrainingStatusResponse(
        task_id=task_id,
        status=result.state.lower(),
        error_message=error_msg,
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
