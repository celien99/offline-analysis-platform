from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.common.logging import get_logger
from app.schemas.common import ErrorResponse
from app.schemas.graph import (
    BuildGraphRequest,
    FindPathRequest,
    GraphBuildStatusResponse,
    GraphEdgeResponse,
    GraphNodeResponse,
    GraphQueryResultResponse,
    NeighborWithScore,
    SubgraphResponse,
)
from app.services.graph import GraphService

router = APIRouter(prefix="/api/graph", tags=["similarity_graph"])
logger = get_logger(__name__)


# ── 图谱构建 ──────────────────────────────────────

@router.post("/build", status_code=202)
async def build_similarity_graph(
    request: BuildGraphRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    service = GraphService(session)
    record = await service.build_graph(k=request.k)
    return {
        "message": "图谱构建完成",
        "build_id": record.id,
        "status": record.status,
        "total_edges": str(record.total_edges),
    }


@router.get("/build/status", response_model=GraphBuildStatusResponse)
async def get_graph_build_status(
    session: AsyncSession = Depends(get_session),
) -> GraphBuildStatusResponse:
    service = GraphService(session)
    status = await service.get_build_status()
    return GraphBuildStatusResponse(**status)


# ── 邻居查询 ──────────────────────────────────────

@router.get(
    "/neighbors/{anomaly_id}",
    response_model=GraphQueryResultResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_neighbors(
    anomaly_id: str,
    k: int = Query(default=10, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
) -> GraphQueryResultResponse:
    service = GraphService(session)
    result = await service.get_neighbors(anomaly_id, k=k)
    if not result.nodes:
        raise HTTPException(status_code=404, detail="Anomaly not found or graph not built")
    return _query_result_to_response(result)


# ── 路径查询 ──────────────────────────────────────

@router.post("/path", response_model=GraphQueryResultResponse)
async def find_path(
    request: FindPathRequest,
    session: AsyncSession = Depends(get_session),
) -> GraphQueryResultResponse:
    service = GraphService(session)
    result = await service.find_path(
        request.source_id,
        request.target_id,
        max_hops=request.max_hops,
    )
    return _query_result_to_response(result)


# ── 子图查询 ──────────────────────────────────────

@router.get(
    "/subgraph/{anomaly_id}",
    response_model=SubgraphResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_subgraph(
    anomaly_id: str,
    k: int = Query(default=10, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
) -> SubgraphResponse:
    service = GraphService(session)
    subgraph = await service.get_subgraph(anomaly_id, k=k)
    if subgraph is None:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    return SubgraphResponse(
        center_node=_node_to_response(subgraph.center_node),
        neighbors=[
            NeighborWithScore(node=_node_to_response(n), similarity_score=s)
            for n, s in subgraph.neighbors
        ],
        edges=[_edge_to_response(e) for e in subgraph.edges],
    )


# ── 辅助函数 ──────────────────────────────────────

def _node_to_response(node) -> GraphNodeResponse:
    return GraphNodeResponse(
        anomaly_id=node.anomaly_id,
        camera_id=node.camera_id,
        cluster_id=node.cluster_id,
        cluster_name=node.cluster_name,
        defect_type=node.defect_type,
        umap_x=node.umap_x,
        umap_y=node.umap_y,
    )


def _edge_to_response(edge) -> GraphEdgeResponse:
    return GraphEdgeResponse(
        source_anomaly_id=edge.source_anomaly_id,
        target_anomaly_id=edge.target_anomaly_id,
        similarity_score=edge.similarity_score,
        rank=edge.rank,
    )


def _query_result_to_response(result) -> GraphQueryResultResponse:
    return GraphQueryResultResponse(
        nodes=[_node_to_response(n) for n in result.nodes],
        edges=[_edge_to_response(e) for e in result.edges],
    )
