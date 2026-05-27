from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.common.logging import get_logger
from app.schemas.common import StatusResponse
from app.core.config import settings
from app.core.exceptions import AppError
from app.schemas.registry import (
    DeploymentResponse,
    ModelDeployRequest,
    ModelOption,
    ModelRegisterRequest,
)
from app.services.training.service import TrainingService
from app.services.deployment.service import DeploymentService

router = APIRouter(prefix="/api/model", tags=["registry"])
logger = get_logger(__name__)


@router.post("/deploy", response_model=DeploymentResponse)
async def deploy_model(
    request: ModelDeployRequest,
    session: AsyncSession = Depends(get_session),
) -> DeploymentResponse:
    service = DeploymentService(session)
    try:
        deployment = await service.deploy_model(
            model_name=request.model_name,
            version=request.version,
            target=request.target,
            deployed_by=request.deployed_by,
        )
    except AppError as exc:
        logger.warning("deploy_failed", error=exc.message, code=exc.code)
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
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
    # 批量加载关联的 ModelVersion，填充 model_name/version
    from app.repositories.registry.model_version import ModelVersionRepository
    mv_repo = ModelVersionRepository(session)
    mv_ids = list({d.model_version_id for d in deployments})
    mv_map = await mv_repo.get_by_ids(mv_ids)

    return [
        DeploymentResponse(
            deployment_id=d.id,
            model_version_id=d.model_version_id,
            model_name=mv_map[d.model_version_id].model_name if d.model_version_id in mv_map else None,
            version=mv_map[d.model_version_id].version if d.model_version_id in mv_map else None,
            target=d.target,
            deployed_by=d.deployed_by,
            deployed_at=d.deployed_at,
            previous_version=d.previous_version,
            deployment_status=d.deployment_status,
        )
        for d in deployments
    ]


@router.get("/options", response_model=list[ModelOption])
async def list_model_options(
    model_type: str | None = Query(default=None, description="按类型筛选: yolo / efficientad / filter_classifier / embedding"),
    session: AsyncSession = Depends(get_session),
) -> list[ModelOption]:
    """获取已注册模型列表，供相机配置页下拉框使用。"""
    service = TrainingService(session)
    models, _ = await service.list_models(model_type=model_type, offset=0, limit=500)
    return [
        ModelOption(
            model_id=m.id,
            model_name=m.model_name,
            version=m.version,
            model_type=m.model_type,
            artifact_path=m.artifact_path,
        )
        for m in models
    ]


@router.post("/register", response_model=ModelOption, status_code=201)
async def register_model(
    request: ModelRegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> ModelOption:
    """手动注册外部模型（如 YOLO），校验文件路径存在。"""
    from pathlib import Path

    artifact_path = Path(request.artifact_path)
    if not artifact_path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"模型文件不存在: {request.artifact_path}",
        )
    if not artifact_path.is_file():
        raise HTTPException(
            status_code=400,
            detail=f"路径不是文件: {request.artifact_path}",
        )

    service = TrainingService(session)
    model = await service.create_model_version(
        model_name=request.model_name,
        version=request.version,
        model_type=request.model_type,
        artifact_path=str(artifact_path.absolute()),
    )
    await session.commit()
    return ModelOption(
        model_id=model.id,
        model_name=model.model_name,
        version=model.version,
        model_type=model.model_type,
        artifact_path=model.artifact_path,
    )
