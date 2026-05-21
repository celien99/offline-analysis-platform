from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.common.logging import get_logger
from app.schemas.common import ErrorResponse
from app.schemas.review import KnowledgeEntryRequest, KnowledgeEntryResponse
from app.services.knowledge import KnowledgeService

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])
logger = get_logger(__name__)


@router.post("/entries", response_model=KnowledgeEntryResponse, status_code=201)
async def create_knowledge_entry(
    request: KnowledgeEntryRequest,
    session: AsyncSession = Depends(get_session),
) -> KnowledgeEntryResponse:
    service = KnowledgeService(session)
    entry = await service.create_entry(
        category=request.category,
        title=request.title,
        description=request.description,
        cluster_id=request.cluster_id,
        defect_type=request.defect_type,
        action=request.action,
        camera_ids=request.camera_ids if request.camera_ids else None,
    )
    return _entry_to_response(entry)


@router.get("/entries", response_model=dict)
async def list_knowledge_entries(
    category: str | None = Query(default=None),
    defect_type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> dict:
    service = KnowledgeService(session)
    offset = (page - 1) * page_size
    entries, total = await service.list_entries(
        category=category,
        defect_type=defect_type,
        offset=offset,
        limit=page_size,
    )
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "items": [_entry_to_response(e) for e in entries],
    }


@router.get("/entries/search", response_model=list[KnowledgeEntryResponse])
async def search_knowledge_entries(
    q: str = Query(..., min_length=1, description="Search keyword"),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> list[KnowledgeEntryResponse]:
    service = KnowledgeService(session)
    entries = await service.search(q, limit=limit)
    return [_entry_to_response(e) for e in entries]


@router.get(
    "/entries/{knowledge_id}",
    response_model=KnowledgeEntryResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_knowledge_entry(
    knowledge_id: str,
    session: AsyncSession = Depends(get_session),
) -> KnowledgeEntryResponse:
    service = KnowledgeService(session)
    entry = await service.get_entry(knowledge_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Knowledge entry {knowledge_id} not found")
    return _entry_to_response(entry)


@router.get(
    "/clusters/{cluster_id}/entries",
    response_model=list[KnowledgeEntryResponse],
)
async def get_cluster_knowledge(
    cluster_id: str,
    session: AsyncSession = Depends(get_session),
) -> list[KnowledgeEntryResponse]:
    service = KnowledgeService(session)
    entries = await service.list_by_cluster(cluster_id)
    return [_entry_to_response(e) for e in entries]


@router.put("/entries/{knowledge_id}", response_model=KnowledgeEntryResponse)
async def update_knowledge_entry(
    knowledge_id: str,
    request: KnowledgeEntryRequest,
    session: AsyncSession = Depends(get_session),
) -> KnowledgeEntryResponse:
    service = KnowledgeService(session)
    entry = await service.update_entry(
        knowledge_id,
        title=request.title,
        description=request.description,
        action=request.action,
    )
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Knowledge entry {knowledge_id} not found")
    return _entry_to_response(entry)


@router.delete("/entries/{knowledge_id}", status_code=204)
async def delete_knowledge_entry(
    knowledge_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    service = KnowledgeService(session)
    await service.delete_entry(knowledge_id)


def _entry_to_response(entry) -> KnowledgeEntryResponse:
    import json
    camera_ids = json.loads(entry.camera_ids) if entry.camera_ids else []
    return KnowledgeEntryResponse(
        knowledge_id=entry.id,
        cluster_id=entry.cluster_id,
        category=entry.category,
        defect_type=entry.defect_type,
        title=entry.title,
        description=entry.description,
        action=entry.action,
        camera_ids=camera_ids,
        created_at=entry.created_at,
    )
