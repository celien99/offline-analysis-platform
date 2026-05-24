from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.common.logging import get_logger
from app.schemas.common import StatusResponse
from app.services.rule_engine import RuleEngineService

router = APIRouter(prefix="/api/rules", tags=["rules"])
logger = get_logger(__name__)


@router.post("/evaluate")
async def evaluate_rules(
    camera_id: str = Query(...),
    defect_type: str | None = Query(default=None),
    anomaly_score: float | None = Query(default=None),
    classifier_prediction: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    service = RuleEngineService(session)
    return await service.evaluate(
        camera_id=camera_id,
        defect_type=defect_type,
        anomaly_score=anomaly_score,
        classifier_prediction=classifier_prediction,
    )


@router.post("", response_model=dict, status_code=201)
async def create_rule(
    name: str = Query(...),
    rule_type: str = Query(..., pattern=r"^(ignore|flag|escalate)$"),
    condition_json: str = Query(..., description="JSON rule condition"),
    priority: int = Query(default=0),
    camera_ids: str | None = Query(default=None, description="Comma-separated camera IDs"),
    knowledge_entry_id: str | None = Query(default=None),
    description: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    import json

    service = RuleEngineService(session)
    condition = json.loads(condition_json)
    cam_ids = camera_ids.split(",") if camera_ids else None

    rule = await service.create_rule(
        name=name,
        rule_type=rule_type,
        condition=condition,
        priority=priority,
        camera_ids=cam_ids,
        knowledge_entry_id=knowledge_entry_id,
        description=description,
    )
    return {
        "rule_id": rule.id,
        "name": rule.name,
        "rule_type": rule.rule_type,
        "priority": rule.priority,
        "enabled": rule.enabled,
        "created_at": rule.created_at.isoformat(),
    }


@router.get("", response_model=dict)
async def list_rules(
    rule_type: str | None = Query(default=None),
    enabled: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> dict:
    service = RuleEngineService(session)
    offset = (page - 1) * page_size
    rules, total = await service.list_rules(
        rule_type=rule_type,
        enabled=enabled,
        offset=offset,
        limit=page_size,
    )
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "items": [
            {
                "rule_id": r.id,
                "name": r.name,
                "rule_type": r.rule_type,
                "priority": r.priority,
                "enabled": r.enabled,
                "description": r.description,
                "created_at": r.created_at.isoformat(),
            }
            for r in rules
        ],
    }


@router.post("/deploy")
async def deploy_rules(
    target: str = Query(default="production_line_a"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    """将启用的规则部署到目标目录，供在线系统加载。"""
    from app.services.deployment.rule_deployment import RuleDeploymentService
    svc = RuleDeploymentService(session)
    dest = await svc.deploy_to_target(target)
    rules_json = await svc.export_rules_json()
    return {
        "status": "deployed",
        "target": target,
        "destination": dest,
        "rule_count": len(rules_json),
    }


@router.get("/preview")
async def preview_rules(
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, object]]:
    """预览将要部署的规则 JSON（不实际写入文件）。"""
    from app.services.deployment.rule_deployment import RuleDeploymentService
    svc = RuleDeploymentService(session)
    return await svc.export_rules_json()


@router.post("/generate-from-knowledge")
async def generate_rules_from_knowledge(
    knowledge_entry_id: str = Query(...),
    camera_ids: str | None = Query(default=None, description="Comma-separated"),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    service = RuleEngineService(session)
    cam_ids = camera_ids.split(",") if camera_ids else None
    rules = await service.auto_generate_rules_from_knowledge(
        knowledge_entry_id=knowledge_entry_id,
        camera_ids=cam_ids,
    )
    return [
        {"rule_id": r.id, "name": r.name, "rule_type": r.rule_type}
        for r in rules
    ]


# ── 以下路由包含路径参数，必须放在固定路径之后 ──

@router.get("/{rule_id}", response_model=dict)
async def get_rule(
    rule_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    service = RuleEngineService(session)
    rule = await service.get_rule(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    return {
        "rule_id": rule.id,
        "name": rule.name,
        "rule_type": rule.rule_type,
        "condition": rule.condition_json,
        "priority": rule.priority,
        "enabled": rule.enabled,
        "camera_ids": rule.camera_ids,
        "description": rule.description,
        "created_at": rule.created_at.isoformat(),
    }


@router.post("/{rule_id}/toggle", response_model=StatusResponse)
async def toggle_rule(
    rule_id: str,
    enabled: bool = Query(...),
    session: AsyncSession = Depends(get_session),
) -> StatusResponse:
    service = RuleEngineService(session)
    rule = await service.toggle_rule(rule_id, enabled)
    if rule is None:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    return StatusResponse(
        status="updated",
        message=f"Rule {rule_id} {'enabled' if enabled else 'disabled'}",
    )


@router.delete("/{rule_id}", status_code=204)
async def delete_rule(
    rule_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    service = RuleEngineService(session)
    await service.delete_rule(rule_id)
