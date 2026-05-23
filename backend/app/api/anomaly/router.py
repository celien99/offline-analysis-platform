from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_minio, get_session
from app.common.logging import get_logger
from app.infrastructure.storage.minio_client import MinIOClient
from app.models.anomaly import AnomalyRecord
from app.schemas.anomaly import (
    AnomalyResponse,
    AnomalyUploadRequest,
    AnomalyUploadResponse,
)
from app.schemas.common import ErrorResponse
from app.services.anomaly import AnomalyService

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
    service = AnomalyService(session, minio)
    anomaly = await service.create_anomaly(
        camera_id=request.camera_id,
        source=request.source,
        anomaly_score=request.anomaly_score,
        date_folder=request.date_folder,
        detected_at=request.detected_at,
        metadata_json=str(request.metadata) if request.metadata else None,
    )
    return AnomalyUploadResponse(anomaly_id=anomaly.id, status="received")


@router.post(
    "/upload-with-files",
    response_model=AnomalyUploadResponse,
    responses={400: {"model": ErrorResponse}},
)
async def upload_anomaly_with_files(
    camera_id: str = Form(..., max_length=64),
    source: str = Form(
        default="patchcore", pattern=r"^(patchcore|filter_classifier|rule_engine)$"
    ),
    anomaly_score: float | None = Form(default=None, ge=0.0),
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

    detected_dt = datetime.fromisoformat(detected_at)

    async def _read(f: UploadFile | None) -> bytes | None:
        if f is None:
            return None
        return await f.read()

    service = AnomalyService(session, minio)
    anomaly = await service.create_anomaly_with_files(
        camera_id=camera_id,
        source=source,
        anomaly_score=anomaly_score,
        date_folder=date_folder,
        detected_at=detected_dt,
        original_data=await _read(original_file),
        roi_data=await _read(roi_file),
        heatmap_data=await _read(heatmap_file),
        crop_data=await _read(crop_file),
        original_content_type=original_file.content_type if original_file else "image/jpeg",
        roi_content_type=roi_file.content_type if roi_file else "image/jpeg",
        heatmap_content_type=heatmap_file.content_type if heatmap_file else "image/jpeg",
        crop_content_type=crop_file.content_type if crop_file else "image/jpeg",
    )
    return AnomalyUploadResponse(anomaly_id=anomaly.id, status="received")


@router.get(
    "/list",
    response_model=dict,
)
async def list_anomalies(
    camera_id: str | None = Query(default=None),
    source: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    minio: MinIOClient = Depends(get_minio),
) -> dict:
    service = AnomalyService(session, minio)
    offset = (page - 1) * page_size
    records, total = await service.list_anomalies(
        camera_id=camera_id,
        source=source,
        status=status,
        offset=offset,
        limit=page_size,
    )
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "items": await asyncio.gather(*[_to_response(r, minio) for r in records]),
    }


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
    service = AnomalyService(session, minio)
    record = await service.get_anomaly(anomaly_id)
    return await _to_response(record, minio)


@router.post("/{anomaly_id}/reprocess")
async def reprocess_anomaly(
    anomaly_id: str,
    session: AsyncSession = Depends(get_session),
    minio: MinIOClient = Depends(get_minio),
) -> dict[str, str]:
    service = AnomalyService(session, minio)
    await service.reprocess_anomaly(anomaly_id)
    return {"status": "queued", "anomaly_id": anomaly_id}


@router.delete(
    "/{anomaly_id}",
    responses={404: {"model": ErrorResponse}},
)
async def delete_anomaly(
    anomaly_id: str,
    session: AsyncSession = Depends(get_session),
    minio: MinIOClient = Depends(get_minio),
) -> dict[str, str]:
    """软删除异常记录（设置 deleted_at）。"""
    service = AnomalyService(session, minio)
    await service.soft_delete_anomaly(anomaly_id)
    return {"status": "deleted", "anomaly_id": anomaly_id}


async def _to_response(record: AnomalyRecord, minio: MinIOClient) -> AnomalyResponse:
    async def _presigned(path: str | None) -> str | None:
        if path is None:
            return None
        try:
            return await minio.get_presigned_url(path)
        except Exception:
            return None

    original_url, roi_url, heatmap_url, crop_url = await asyncio.gather(
        _presigned(record.original_path),
        _presigned(record.roi_path),
        _presigned(record.heatmap_path),
        _presigned(record.crop_path),
    )
    return AnomalyResponse(
        anomaly_id=record.id,
        camera_id=record.camera_id,
        source=record.source,
        anomaly_score=record.anomaly_score,
        date_folder=record.date_folder,
        status=record.status,
        detected_at=record.detected_at,
        original_url=original_url,
        roi_url=roi_url,
        heatmap_url=heatmap_url,
        crop_url=crop_url,
        created_at=record.created_at,
        trace_id=record.trace_id,
    )
