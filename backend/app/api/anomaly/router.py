from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_minio, get_session
from app.common.logging import get_logger
from app.core.security import generate_trace_id, generate_uuid
from app.infrastructure.storage.minio_client import MinIOClient
from app.models.anomaly import AnomalyRecord
from app.repositories.anomaly.repository import AnomalyRepository
from app.schemas.anomaly import (
    AnomalyResponse,
    AnomalyUploadRequest,
    AnomalyUploadResponse,
)
from app.schemas.common import ErrorResponse

router = APIRouter(prefix="/api/anomaly", tags=["anomaly"])
logger = get_logger(__name__)


@router.post(
    "/upload",
    response_model=AnomalyUploadResponse,
    responses={400: {"model": ErrorResponse}},
)
async def upload_anomaly(
    request: AnomalyUploadRequest,
    session: AsyncSession = Depends(get_session),
    minio: MinIOClient = Depends(get_minio),
) -> AnomalyUploadResponse:
    trace_id = generate_trace_id()
    logger.info("anomaly_upload", camera_id=request.camera_id, trace_id=trace_id)

    repo = AnomalyRepository(session)
    anomaly = AnomalyRecord(
        id=generate_uuid(),
        camera_id=request.camera_id,
        source=request.source,
        anomaly_score=request.anomaly_score,
        date_folder=request.date_folder,
        detected_at=request.detected_at,
        metadata_json=str(request.metadata) if request.metadata else None,
        status="pending",
        trace_id=trace_id,
    )
    await repo.create(anomaly)

    logger.info(
        "anomaly_created",
        anomaly_id=anomaly.id,
        trace_id=trace_id,
    )
    return AnomalyUploadResponse(
        anomaly_id=anomaly.id,
        status="received",
    )


@router.post(
    "/upload-with-files",
    response_model=AnomalyUploadResponse,
    responses={400: {"model": ErrorResponse}},
)
async def upload_anomaly_with_files(
    camera_id: str = Form(..., max_length=64),
    source: str = Form(default="patchcore", pattern=r"^(patchcore|filter_classifier|rule_engine)$"),
    anomaly_score: float | None = Form(default=None, ge=0.0, le=1.0),
    date_folder: str = Form(..., max_length=16),
    detected_at: str = Form(...),
    original_file: UploadFile | None = File(default=None),
    roi_file: UploadFile | None = File(default=None),
    heatmap_file: UploadFile | None = File(default=None),
    crop_file: UploadFile | None = File(default=None),
    session: AsyncSession = Depends(get_session),
    minio: MinIOClient = Depends(get_minio),
) -> AnomalyUploadResponse:
    from datetime import datetime

    trace_id = generate_trace_id()
    anomaly_id = generate_uuid()
    detected_dt = datetime.fromisoformat(detected_at)

    base_path = f"anomaly_data/{date_folder}/{camera_id}/{anomaly_id}"

    async def _save(upload_file: UploadFile | None, suffix: str) -> str | None:
        if upload_file is None:
            return None
        content = await upload_file.read()
        path = f"{base_path}_{suffix}.jpg"
        await minio.upload(path, content, upload_file.content_type or "image/jpeg")
        return path

    original_path = await _save(original_file, "original")
    roi_path = await _save(roi_file, "roi")
    heatmap_path = await _save(heatmap_file, "heatmap")
    crop_path = await _save(crop_file, "crop")

    repo = AnomalyRepository(session)
    anomaly = AnomalyRecord(
        id=anomaly_id,
        camera_id=camera_id,
        source=source,
        anomaly_score=anomaly_score,
        date_folder=date_folder,
        detected_at=detected_dt,
        original_path=original_path,
        roi_path=roi_path,
        heatmap_path=heatmap_path,
        crop_path=crop_path,
        status="pending",
        trace_id=trace_id,
    )
    await repo.create(anomaly)

    logger.info(
        "anomaly_created_with_files",
        anomaly_id=anomaly.id,
        trace_id=trace_id,
        has_original=original_path is not None,
        has_crop=crop_path is not None,
    )
    return AnomalyUploadResponse(
        anomaly_id=anomaly.id,
        status="received",
    )


@router.get(
    "/list",
    response_model=list[AnomalyResponse],
)
async def list_anomalies(
    camera_id: str | None = Query(default=None),
    source: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    minio: MinIOClient = Depends(get_minio),
) -> list[AnomalyResponse]:
    repo = AnomalyRepository(session)
    offset = (page - 1) * page_size
    records = await repo.list_all(
        camera_id=camera_id,
        source=source,
        status=status,
        offset=offset,
        limit=page_size,
    )
    return [_to_response(r, minio) for r in records]


@router.get(
    "/{anomaly_id}",
    response_model=AnomalyResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_anomaly(
    anomaly_id: str,
    session: AsyncSession = Depends(get_session),
    minio: MinIOClient = Depends(get_minio),
) -> AnomalyResponse:
    repo = AnomalyRepository(session)
    record = await repo.get_by_id(anomaly_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Anomaly {anomaly_id} not found")
    return _to_response(record, minio)


@router.post("/{anomaly_id}/reprocess")
async def reprocess_anomaly(
    anomaly_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    repo = AnomalyRepository(session)
    record = await repo.get_by_id(anomaly_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Anomaly {anomaly_id} not found")

    await repo.update_status(anomaly_id, "pending")
    logger.info("anomaly_reprocess_queued", anomaly_id=anomaly_id)
    return {"status": "queued", "anomaly_id": anomaly_id}


def _to_response(record: AnomalyRecord, minio: MinIOClient) -> AnomalyResponse:
    def _presigned(path: str | None) -> str | None:
        if path is None:
            return None
        try:
            return minio.get_presigned_url(path)
        except Exception:
            return None

    return AnomalyResponse(
        anomaly_id=record.id,
        camera_id=record.camera_id,
        source=record.source,
        anomaly_score=record.anomaly_score,
        date_folder=record.date_folder,
        status=record.status,
        detected_at=record.detected_at,
        original_url=_presigned(record.original_path),
        roi_url=_presigned(record.roi_path),
        heatmap_url=_presigned(record.heatmap_path),
        crop_url=_presigned(record.crop_path),
        created_at=record.created_at,
        trace_id=record.trace_id,
    )
