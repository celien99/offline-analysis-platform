from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_minio, get_session
from app.common.logging import get_logger
from app.infrastructure.storage.minio_client import MinIOClient
from app.repositories.anomaly.repository import AnomalyRepository
from app.services.clustering.service import ClusteringService
from app.schemas.cluster import (
    ClusterDetailResponse,
    ClusterListResponse,
    ClusterSummary,
    ClusterTriggerRequest,
)
from app.schemas.common import ErrorResponse, StatusResponse
from app.workers.clustering_worker.tasks import run_clustering

router = APIRouter(prefix="/api/cluster", tags=["cluster"])
logger = get_logger(__name__)


async def _resolve_image_urls(
    representative_ids: list[str],
    session,
    minio: MinIOClient,
) -> list[str]:
    """将 representative_ids (anomaly IDs) 解析为 presigned MinIO URL。"""
    if not representative_ids:
        return []
    anomaly_repo = AnomalyRepository(session)
    anomalies = await anomaly_repo.get_by_ids(representative_ids)
    id_to_crop = {a.id: a.crop_path for a in anomalies if a.crop_path}

    urls: list[str] = []
    for aid in representative_ids:
        crop_path = id_to_crop.get(aid)
        if crop_path:
            try:
                urls.append(await minio.get_presigned_url(crop_path, expires_seconds=3600))
            except Exception:
                urls.append("")
        else:
            urls.append("")
    return urls


@router.get("/list", response_model=ClusterListResponse)
async def list_clusters(
    status: str | None = Query(default=None),
    review_status: str | None = Query(default=None),
    defect_type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    minio: MinIOClient = Depends(get_minio),
) -> ClusterListResponse:
    service = ClusteringService(session)
    offset = (page - 1) * page_size
    clusters, total = await service.list_clusters(
        status=status,
        offset=offset,
        limit=page_size,
    )

    summaries: list[ClusterSummary] = []
    for c in clusters:
        rep_ids = json.loads(c.representative_ids or "[]")
        urls = await _resolve_image_urls(rep_ids, session, minio)
        summaries.append(ClusterSummary(
            cluster_id=c.id,
            name=c.name,
            sample_count=c.sample_count,
            possible_type=c.possible_type,
            hdbscan_label=c.hdbscan_label,
            hdbscan_probability=c.hdbscan_probability,
            umap_x=c.umap_x,
            umap_y=c.umap_y,
            status=c.status,
            review_status=c.review_status,
            defect_type=c.defect_type,
            representative_image_urls=urls,
            reviewed_by=c.reviewed_by,
            reviewed_at=c.reviewed_at,
            vlm_anomaly_type=_vlm_value(c.vlm_analysis_json, "anomaly_type"),
            vlm_is_false_alarm=_vlm_value(c.vlm_analysis_json, "is_false_alarm"),
            vlm_analyzed_at=c.vlm_analyzed_at,
            created_at=c.created_at,
        ))

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    return ClusterListResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        clusters=summaries,
    )


@router.get("/visualization")
async def get_cluster_visualization(
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    """Return cluster data formatted for Plotly scatter plot visualization."""
    service = ClusteringService(session)
    clusters, _ = await service.list_clusters(offset=0, limit=10000)

    scatter_data: list[dict[str, object]] = []
    summary: dict[str, int] = {
        "total_clusters": 0,
        "total_samples": 0,
        "real_defect": 0,
        "false_alarm": 0,
        "pending_review": 0,
    }

    for c in clusters:
        if c.umap_x is not None and c.umap_y is not None:
            scatter_data.append({
                "cluster_id": c.id,
                "name": c.name or f"Cluster {c.id[:8]}",
                "x": c.umap_x,
                "y": c.umap_y,
                "sample_count": c.sample_count,
                "possible_type": c.possible_type or "unknown",
                "review_status": c.review_status or "pending_review",
                "defect_type": c.defect_type or "unknown",
            })

        summary["total_clusters"] += 1
        summary["total_samples"] += c.sample_count
        if c.review_status == "real_defect":
            summary["real_defect"] += 1
        elif c.review_status == "false_alarm":
            summary["false_alarm"] += 1
        else:
            summary["pending_review"] += 1

    return {
        "scatter_data": scatter_data,
        "summary": summary,
    }


@router.get(
    "/{cluster_id}",
    response_model=ClusterDetailResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_cluster_detail(
    cluster_id: str,
    session: AsyncSession = Depends(get_session),
    minio: MinIOClient = Depends(get_minio),
) -> ClusterDetailResponse:
    service = ClusteringService(session)
    cluster = await service.get_cluster_detail(cluster_id)
    if cluster is None:
        raise HTTPException(status_code=404, detail=f"Cluster {cluster_id} not found")

    rep_ids = json.loads(cluster.representative_ids or "[]")
    urls = await _resolve_image_urls(rep_ids, session, minio)
    centroid = json.loads(cluster.centroid) if cluster.centroid else None

    return ClusterDetailResponse(
        cluster_id=cluster.id,
        name=cluster.name,
        sample_count=cluster.sample_count,
        possible_type=cluster.possible_type,
        hdbscan_label=cluster.hdbscan_label,
        hdbscan_probability=cluster.hdbscan_probability,
        umap_x=cluster.umap_x,
        umap_y=cluster.umap_y,
        status=cluster.status,
        review_status=cluster.review_status,
        defect_type=cluster.defect_type,
        representative_ids=rep_ids,
        representative_image_urls=urls,
        centroid=centroid,
        reviewed_by=cluster.reviewed_by,
        reviewed_at=cluster.reviewed_at,
        vlm_anomaly_type=_vlm_value(cluster.vlm_analysis_json, "anomaly_type"),
        vlm_is_false_alarm=_vlm_value(cluster.vlm_analysis_json, "is_false_alarm"),
        vlm_reason=_vlm_value(cluster.vlm_analysis_json, "reason"),
        vlm_confidence=_vlm_value(cluster.vlm_analysis_json, "confidence"),
        vlm_suggestion=_vlm_value(cluster.vlm_analysis_json, "suggestion"),
        vlm_analyzed_at=cluster.vlm_analyzed_at,
        clustering_run_at=cluster.clustering_run_at,
        created_at=cluster.created_at,
        trace_id=cluster.trace_id,
    )


def _vlm_value(payload: str | None, key: str) -> object | None:
    if not payload:
        return None
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None
    return data.get(key)


@router.get("/{cluster_id}/anomalies")
async def get_cluster_anomalies(
    cluster_id: str,
    session: AsyncSession = Depends(get_session),
    minio: MinIOClient = Depends(get_minio),
) -> list[dict[str, object]]:
    """获取某个 cluster 下所有 anomaly 的基本信息（含 presigned URL）。"""
    from app.repositories.anomaly.repository import AnomalyRepository
    from app.schemas.anomaly import AnomalyResponse

    membership_repo = ClusterMembershipRepository(session)
    anomaly_ids = await membership_repo.get_anomaly_ids_by_cluster(cluster_id)
    if not anomaly_ids:
        return []

    anomaly_repo = AnomalyRepository(session)
    anomalies = await anomaly_repo.get_by_ids(anomaly_ids)

    results: list[dict[str, object]] = []
    for a in anomalies:
        crop_url = None
        if a.crop_path:
            try:
                crop_url = await minio.get_presigned_url(a.crop_path, expires_seconds=3600)
            except Exception:
                pass
        results.append({
            "anomaly_id": a.id,
            "camera_id": a.camera_id,
            "anomaly_score": a.anomaly_score,
            "status": a.status,
            "crop_url": crop_url,
            "detected_at": a.detected_at.isoformat() if a.detected_at else None,
        })
    return results


@router.post("/trigger", response_model=StatusResponse)
async def trigger_clustering(
    request: ClusterTriggerRequest,
) -> StatusResponse:
    task = run_clustering.delay(
        min_cluster_size=request.min_cluster_size,
        min_samples=request.min_samples,
        anomaly_ids=request.anomaly_ids,
    )
    logger.info("clustering_triggered", task_id=task.id)
    return StatusResponse(
        status="queued",
        message=f"Clustering task {task.id} dispatched",
    )
