from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.common.logging import get_logger
from app.repositories.anomaly.repository import AnomalyRepository
from app.workers.mask_refinement_worker.tasks import refine_batch, refine_single_anomaly

router = APIRouter(prefix="/api/mask-refinement", tags=["mask_refinement"])
logger = get_logger(__name__)


@router.post("/refine/{anomaly_id}", status_code=202)
async def refine_anomaly(
    anomaly_id: str,
    use_grabcut: bool = Query(default=True),
    equalize_hist: bool = Query(default=True),
    session: AsyncSession = Depends(get_session),
) -> dict:
    repo = AnomalyRepository(session)
    anomaly = await repo.get_by_id(anomaly_id)
    if anomaly is None:
        raise HTTPException(status_code=404, detail=f"Anomaly {anomaly_id} not found")
    if anomaly.crop_path is None:
        raise HTTPException(status_code=400, detail="Anomaly has no crop image")

    task = refine_single_anomaly.delay(
        anomaly_id=anomaly_id,
        crop_path=anomaly.crop_path,
        use_grabcut=use_grabcut,
        equalize_hist=equalize_hist,
    )
    logger.info("mask_refine_dispatched", anomaly_id=anomaly_id, task_id=str(task.id))
    return {"status": "queued", "task_id": str(task.id), "anomaly_id": anomaly_id}


@router.post("/refine-batch", status_code=202)
async def refine_batch_anomalies(
    batch_size: int = Query(default=100, ge=1, le=500),
) -> dict:
    result = refine_batch.delay(batch_size=batch_size)
    return {"status": "queued", "batch_task_id": str(result.id)}
