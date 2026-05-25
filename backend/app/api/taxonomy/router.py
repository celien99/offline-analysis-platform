from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.common.logging import get_logger
from app.models.taxonomy import DefectTreeNode
from app.schemas.common import ErrorResponse
from app.schemas.taxonomy import (
    AutoClassifyRequest,
    AutoClassifyResponse,
    LinkKnowledgeRequest,
    TaxonomyNodeCreateRequest,
    TaxonomyNodeResponse,
    TaxonomyNodeUpdateRequest,
    TaxonomyStatsResponse,
    TaxonomyTreeResponse,
)
from app.services.taxonomy import TaxonomyService

router = APIRouter(prefix="/api/taxonomy", tags=["taxonomy"])
logger = get_logger(__name__)


def _node_to_response(node: DefectTreeNode) -> TaxonomyNodeResponse:
    return TaxonomyNodeResponse(
        node_id=node.id,
        name=node.name,
        parent_id=node.parent_id,
        level=node.level,
        description=node.description,
        defect_type=node.defect_type,
        icon=node.icon,
    )


def _domain_node_to_response(tn: Any) -> TaxonomyNodeResponse:
    return TaxonomyNodeResponse(
        node_id=tn.id,
        name=tn.name,
        parent_id=tn.parent_id,
        level=tn.level,
        description=tn.description,
        defect_type=tn.defect_type,
        icon=tn.icon,
        anomaly_count=tn.anomaly_count,
        children=[_domain_node_to_response(c) for c in tn.children],
    )


def _stats_to_response(stats: Any) -> TaxonomyStatsResponse:
    return TaxonomyStatsResponse(
        node_id=stats.node_id,
        node_name=stats.node_name,
        anomaly_count=stats.anomaly_count,
        cluster_count=stats.cluster_count,
        children_stats=[_stats_to_response(c) for c in stats.children_stats],
    )


# ── 初始化默认分类树 ──────────────────────────────────

@router.post("/init", status_code=201)
async def init_default_taxonomy(
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    service = TaxonomyService(session)
    count = await service.init_default_taxonomy()
    return {"message": f"初始化完成，创建了 {count} 个节点" if count else "分类树已存在，无需初始化", "node_count": count}


# ── 树查询 ──────────────────────────────────────────

@router.get("/tree", response_model=TaxonomyTreeResponse)
async def get_taxonomy_tree(
    session: AsyncSession = Depends(get_session),
) -> TaxonomyTreeResponse:
    service = TaxonomyService(session)
    tree = await service.get_tree()
    return TaxonomyTreeResponse(
        roots=[_domain_node_to_response(r) for r in tree.roots],
        total_nodes=tree.total_nodes,
    )


@router.get(
    "/tree/stats",
    response_model=list[TaxonomyStatsResponse],
)
async def get_tree_statistics(
    session: AsyncSession = Depends(get_session),
) -> list[TaxonomyStatsResponse]:
    service = TaxonomyService(session)
    stats_list = await service.get_tree_stats()
    return [_stats_to_response(s) for s in stats_list]


# ── 节点 CRUD ───────────────────────────────────────

@router.post(
    "/nodes",
    response_model=TaxonomyNodeResponse,
    status_code=201,
    responses={409: {"model": ErrorResponse}},
)
async def create_taxonomy_node(
    request: TaxonomyNodeCreateRequest,
    session: AsyncSession = Depends(get_session),
) -> TaxonomyNodeResponse:
    service = TaxonomyService(session)
    node = await service.create_node(
        name=request.name,
        parent_id=request.parent_id,
        level=request.level,
        description=request.description,
        defect_type=request.defect_type,
        icon=request.icon,
    )
    return _node_to_response(node)


@router.get(
    "/nodes/{node_id}",
    response_model=TaxonomyNodeResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_taxonomy_node(
    node_id: str,
    session: AsyncSession = Depends(get_session),
) -> TaxonomyNodeResponse:
    service = TaxonomyService(session)
    node = await service.get_node(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    return _node_to_response(node)


@router.put(
    "/nodes/{node_id}",
    response_model=TaxonomyNodeResponse,
    responses={404: {"model": ErrorResponse}},
)
async def update_taxonomy_node(
    node_id: str,
    request: TaxonomyNodeUpdateRequest,
    session: AsyncSession = Depends(get_session),
) -> TaxonomyNodeResponse:
    service = TaxonomyService(session)
    node = await service.update_node(
        node_id,
        name=request.name,
        description=request.description,
        defect_type=request.defect_type,
        icon=request.icon,
    )
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    return _node_to_response(node)


@router.delete("/nodes/{node_id}", status_code=204)
async def delete_taxonomy_node(
    node_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    service = TaxonomyService(session)
    await service.delete_node(node_id)


# ── 自动分类 ────────────────────────────────────────

@router.post("/auto-classify", response_model=AutoClassifyResponse)
async def auto_classify_defect(
    request: AutoClassifyRequest,
    session: AsyncSession = Depends(get_session),
) -> AutoClassifyResponse:
    service = TaxonomyService(session)
    node_id = await service.auto_classify(request.defect_type)
    node_name = None
    if node_id:
        node = await service.get_node(node_id)
        if node:
            node_name = node.name
    return AutoClassifyResponse(
        defect_type=request.defect_type,
        matched_node_id=node_id,
        matched_node_name=node_name,
    )


# ── 关联知识条目 ────────────────────────────────────

@router.post("/link-knowledge", status_code=200)
async def link_knowledge_to_taxonomy(
    request: LinkKnowledgeRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    service = TaxonomyService(session)
    await service.link_knowledge_to_taxonomy(
        request.knowledge_id, request.taxonomy_node_id
    )
    return {"message": "关联成功"}


@router.get("/unclassified-entries")
async def get_unclassified_entries(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    service = TaxonomyService(session)
    offset = (page - 1) * page_size
    entries = await service.get_unclassified_entries(offset=offset, limit=page_size)
    return {
        "total": len(entries),
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "knowledge_id": e.id,
                "title": e.title,
                "defect_type": e.defect_type,
                "category": e.category,
            }
            for e in entries
        ],
    }
