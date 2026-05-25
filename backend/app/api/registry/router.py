from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.common.logging import get_logger
from app.schemas.common import StatusResponse
from app.core.config import settings
from app.schemas.registry import (
    DeploymentResponse,
    ModelDeployRequest,
)
from app.services.deployment.service import DeploymentService

router = APIRouter(prefix="/api/model", tags=["registry"])
logger = get_logger(__name__)


@router.post("/deploy", response_model=DeploymentResponse)
async def deploy_model(
    request: ModelDeployRequest,
    session: AsyncSession = Depends(get_session),
) -> DeploymentResponse:
    service = DeploymentService(session)
    deployment = await service.deploy_model(
        model_name=request.model_name,
        version=request.version,
        target=request.target,
        deployed_by=request.deployed_by,
    )
    return DeploymentResponse(
        deployment_id=deployment.id,
        model_version_id=deployment.model_version_id,
        model_name=request.model_name,
        version=request.version,
        target=deployment.target,
        deployed_by=deployment.deployed_by,
        deployed_at=deployment.deployed_at,
        previous_version=deployment.previous_version,
        deployment_status=deployment.deployment_status,
    )


@router.post("/deploy/{target}/rollback")
async def rollback_model(
    target: str,
    reason: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> StatusResponse:
    service = DeploymentService(session)
    await service.rollback(target, reason=reason)
    return StatusResponse(status="rolled_back", message=f"Model for {target} rolled back")


@router.post("/deploy/canary/{deployment_id}/promote")
async def promote_canary(
    deployment_id: str,
    reviewer: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> StatusResponse:
    """推广金丝雀模型到正式目录。"""
    service = DeploymentService(session)
    await service.confirm_canary(deployment_id, reviewer)
    await session.commit()
    return StatusResponse(status="promoted", message=f"Canary {deployment_id} promoted")


@router.post("/deploy/canary/{deployment_id}/rollback")
async def rollback_canary(
    deployment_id: str,
    reason: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> StatusResponse:
    """回滚金丝雀部署。"""
    service = DeploymentService(session)
    await service.rollback_canary(deployment_id, reason)
    await session.commit()
    return StatusResponse(status="rolled_back", message=f"Canary {deployment_id} rolled back")


@router.get("/deploy-targets")
async def list_deploy_targets() -> dict[str, str]:
    """列出所有已配置的部署目标及其目录路径。"""
    return dict(settings.deploy_targets)


@router.get(
    "/deployments",
    response_model=list[DeploymentResponse],
)
async def list_deployments(
    target: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> list[DeploymentResponse]:
    service = DeploymentService(session)
    offset = (page - 1) * page_size
    deployments, _ = await service.list_deployments(
        target=target, offset=offset, limit=page_size
    )
    return [
        DeploymentResponse(
            deployment_id=d.id,
            model_version_id=d.model_version_id,
            target=d.target,
            deployed_by=d.deployed_by,
            deployed_at=d.deployed_at,
            previous_version=d.previous_version,
            deployment_status=d.deployment_status,
        )
        for d in deployments
    ]
