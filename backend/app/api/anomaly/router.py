from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_minio, get_session
from app.common.logging import get_logger
from app.infrastructure.storage.minio_client import MinIOClient
from app.models.anomaly import AnomalyRecord
from app.repositories.cluster.repository import ClusterMembershipRepository
from app.schemas.anomaly import (
    AnomalyResponse,
    AnomalyUploadResponse,
)
from app.schemas.common import ErrorResponse
from app.services.anomaly import AnomalyService

router = APIRouter(prefix="/api/anomaly", tags=["anomaly"])
logger = get_logger(__name__)


@router.post(
    "/upload-with-files",
    response_model=AnomalyUploadResponse,
    responses={400: {"model": ErrorResponse}},
)
async def upload_anomaly_with_files(
    camera_id: str = Form(..., max_length=64),
    seat_model_id: str | None = Form(default=None, max_length=128),
    source: str = Form(
        default="patchcore", pattern=r"^(patchcore|filter_classifier|rule_engine)$"
    ),
    anomaly_score: float | None = Form(default=None, ge=0.0),
    date_folder: str = Form(..., max_length=16),
    detected_at: str = Form(...),
    decision_reason: str | None = Form(default=None, max_length=64),
    filter_confidence: float | None = Form(default=None, ge=0.0, le=1.0),
    filter_real_defect_score: float | None = Form(default=None, ge=0.0, le=1.0),
    filter_false_alarm_score: float | None = Form(default=None, ge=0.0, le=1.0),
    filter_class_id: int | None = Form(default=None, ge=0),
    filter_action: str | None = Form(default=None, max_length=32),
    original_file: UploadFile | None = File(default=None),
    heatmap_file: UploadFile | None = File(default=None),
    crop_files: list[UploadFile] = File(default=[]),
    session: AsyncSession = Depends(get_session),
    minio: MinIOClient = Depends(get_minio),
) -> AnomalyUploadResponse:
    from datetime import datetime

    detected_dt = datetime.fromisoformat(detected_at)

    async def _read(f: UploadFile | None) -> bytes | None:
        if f is None:
            return None
        return await f.read()

    crop_data_list = [await _read(f) for f in crop_files]

    service = AnomalyService(session, minio)
    anomalies = await service.create_anomaly_with_files(
        camera_id=camera_id,
        seat_model_id=seat_model_id,
        source=source,
        anomaly_score=anomaly_score,
        date_folder=date_folder,
        detected_at=detected_dt,
        decision_reason=decision_reason,
        filter_confidence=filter_confidence,
        filter_real_defect_score=filter_real_defect_score,
        filter_false_alarm_score=filter_false_alarm_score,
        filter_class_id=filter_class_id,
        filter_action=filter_action,
        original_data=await _read(original_file),
        heatmap_data=await _read(heatmap_file),
        crop_data_list=crop_data_list,
        original_content_type=original_file.content_type if original_file else "image/jpeg",
        heatmap_content_type=heatmap_file.content_type if heatmap_file else "image/jpeg",
    )
    return AnomalyUploadResponse(
        anomaly_ids=[a.id for a in anomalies],
        count=len(anomalies),
        status="received",
    )


@router.get(
    "/list",
    response_model=dict,
)
async def list_anomalies(
    camera_id: str | None = Query(default=None),
    seat_model_id: str | None = Query(default=None),
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
        seat_model_id=seat_model_id,
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
    "/noise",
    response_model=dict,
)
async def list_noise_anomalies(
    seat_model_id: str | None = Query(default=None),
    camera_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    minio: MinIOClient = Depends(get_minio),
) -> dict:
    """列出未被任何 cluster 包含的噪声异常（HDBSCAN label=-1）。"""
    from app.services.review.noise_service import NoiseReviewService

    service = NoiseReviewService(session)
    offset = (page - 1) * page_size
    records, total = await service.list_noise_anomalies(
        offset=offset, limit=page_size,
        seat_model_id=seat_model_id,
        camera_id=camera_id,
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
    "/filter-stats",
    response_model=dict,
)
async def get_filter_classifier_stats(
    camera_id: str | None = Query(default=None),
    seat_model_id: str | None = Query(default=None),
    days: int = Query(default=7, ge=1, le=90),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """过滤器分类器效果统计，交叉对比人工审核结果。"""
    from datetime import datetime as dt, timedelta, timezone

    from app.repositories.anomaly.repository import AnomalyRepository

    since_dt = dt.now(tz=timezone.utc) - timedelta(days=days)
    repo = AnomalyRepository(session)

    action_counts = await repo.get_filter_stats(
        since=since_dt, camera_id=camera_id, seat_model_id=seat_model_id
    )
    review_breakdown = await repo.get_filter_vs_human_review(
        since=since_dt, camera_id=camera_id, seat_model_id=seat_model_id
    )

    total_with_filter = sum(action_counts.values())
    confirmed_total = action_counts.get("confirmed_ng", 0)
    suppressed_total = action_counts.get("suppressed_to_ok", 0)
    confirmed_correct = sum(
        r["count"]
        for r in review_breakdown
        if r["filter_action"] == "confirmed_ng" and r["human_review"] == "real_defect"
    )
    suppressed_correct = sum(
        r["count"]
        for r in review_breakdown
        if r["filter_action"] == "suppressed_to_ok" and r["human_review"] == "false_alarm"
    )

    return {
        "period_days": days,
        "total_with_filter_decision": total_with_filter,
        "by_action": {
            "confirmed_ng": action_counts.get("confirmed_ng", 0),
            "suppressed_to_ok": action_counts.get("suppressed_to_ok", 0),
            "not_applied": action_counts.get("not_applied", 0),
        },
        "accuracy": {
            "confirmed_precision": (
                confirmed_correct / confirmed_total if confirmed_total > 0 else None
            ),
            "suppressed_precision": (
                suppressed_correct / suppressed_total if suppressed_total > 0 else None
            ),
        },
        "filter_vs_human_review": review_breakdown,
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
    response = await _to_response(record, minio)
    # 查询该 anomaly 所属的 cluster
    membership_repo = ClusterMembershipRepository(session)
    cluster_ids = await membership_repo.get_cluster_ids_by_anomaly(anomaly_id)
    response.cluster_id = cluster_ids[0] if cluster_ids else None
    return response


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

    crop_paths = record.crop_path_list
    crop_url = None
    crop_urls: list[str] = []
    if crop_paths:
        results = await asyncio.gather(*[_presigned(p) for p in crop_paths])
        crop_url = results[0]
        crop_urls = [u for u in results[1:] if u is not None]

    original_url, heatmap_url, refined_crop_url = await asyncio.gather(
        _presigned(record.original_path),
        _presigned(record.heatmap_path),
        _presigned(record.refined_crop_path),
    )
    return AnomalyResponse(
        anomaly_id=record.id,
        camera_id=record.camera_id,
        seat_model_id=record.seat_model_id,
        source=record.source,
        anomaly_score=record.anomaly_score,
        date_folder=record.date_folder,
        status=record.status,
        detected_at=record.detected_at,
        original_url=original_url,
        heatmap_url=heatmap_url,
        crop_url=crop_url,
        crop_urls=crop_urls if crop_urls else [],
        refined_crop_url=refined_crop_url,
        created_at=record.created_at,
        trace_id=record.trace_id,
    )
