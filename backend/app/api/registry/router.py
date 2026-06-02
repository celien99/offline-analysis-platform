from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.common.logging import get_logger
from app.schemas.common import StatusResponse
from app.core.config import settings
from app.core.exceptions import AppError
from app.repositories.camera_config import CameraConfigRepository, SeatModelRepository
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
    available_models = [
        model for model in models if Path(model.artifact_path).is_file()
    ]
    return [
        ModelOption(
            model_id=m.id,
            model_name=m.model_name,
            version=m.version,
            model_type=m.model_type,
            artifact_path=m.artifact_path,
        )
        for m in available_models
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


class BatchTrainImportRequest(BaseModel):
    output_root: str = Field(..., description="batch_train 输出根目录的绝对路径")
    seat_model_id: str = Field(..., description="目标座椅型号 seat_model_id")
    auto_bind: bool = Field(default=True, description="是否自动绑定到同名 CameraConfig")


class BatchTrainImportResult(BaseModel):
    status: str  # "completed" | "partial"
    imported: list[dict[str, Any]]  # [{camera_id, model_type, model_id, model_name, bound}]
    errors: list[str]


@router.post("/import-batch-train", response_model=BatchTrainImportResult)
async def import_batch_train_artifacts(
    request: BatchTrainImportRequest,
    session: AsyncSession = Depends(get_session),
) -> BatchTrainImportResult:
    """扫描 batch_train 的 output_root 目录，自动注册模型并绑定到 CameraConfig。

    识别并导入以下产物：
    - {camera_id}_patchcore.npz → 注册为 patchcore 类型
    - {camera_id}_norm.npz → 注册为 camera_normalizer 类型
    - projector.npz → 注册为 projector 类型

    当 auto_bind=True 时，自动将 camera_id 匹配的模型绑定到对应 CameraConfig。
    全局模型（projector）绑定到 SeatModel。
    """
    output_root = Path(request.output_root)
    if not output_root.is_dir():
        raise HTTPException(status_code=400, detail=f"目录不存在: {request.output_root}")

    seat_repo = SeatModelRepository(session)
    seat_model = await seat_repo.get_by_seat_model_id(request.seat_model_id)
    if not seat_model:
        raise HTTPException(status_code=404, detail=f"座椅型号不存在: {request.seat_model_id}")

    cam_repo = CameraConfigRepository(session)
    train_svc = TrainingService(session)

    imported: list[dict[str, Any]] = []
    errors: list[str] = []

    # 扫描 output_root 目录
    patchcore_files: dict[str, Path] = {}  # camera_id → PatchCore .npz 路径
    norm_files: dict[str, Path] = {}     # camera_id → _norm.npz 路径
    projector_path: Optional[Path] = None

    for f in sorted(output_root.iterdir()):
        if not f.is_file():
            continue
        name = f.name
        if name == "projector.npz":
            projector_path = f
        elif name.endswith("_patchcore.npz"):
            camera_id = name[: -len("_patchcore.npz")]
            patchcore_files[camera_id] = f
        elif name.endswith("_norm.npz"):
            # {camera_id}_norm.npz
            camera_id = name[: -len("_norm.npz")]
            norm_files[camera_id] = f

    # 按 camera_id 导入 PatchCore 模型 + Normalizer
    all_camera_ids = set(patchcore_files.keys()) | set(norm_files.keys())
    for camera_id in sorted(all_camera_ids):
        patchcore_path = patchcore_files.get(camera_id)
        norm_path = norm_files.get(camera_id)

        # 读取 meta.json 获取版本信息
        version = _build_timestamp_version()
        if patchcore_path:
            meta_path = patchcore_path.with_suffix(".meta.json")
            if meta_path.exists():
                try:
                    json.loads(meta_path.read_text("utf-8"))
                except (json.JSONDecodeError, OSError):
                    pass

        # 注册 PatchCore 模型
        if patchcore_path:
            try:
                model_name = f"patchcore_{camera_id}"
                model = await train_svc.create_model_version(
                    model_name=model_name,
                    version=version,
                    model_type="patchcore",
                    artifact_path=str(patchcore_path.absolute()),
                )
                imported.append({
                    "camera_id": camera_id,
                    "model_type": "patchcore",
                    "model_id": model.id,
                    "model_name": model_name,
                    "file": patchcore_path.name,
                })

                if request.auto_bind:
                    cam = await cam_repo.get_by_camera_id(request.seat_model_id, camera_id)
                    if cam:
                        cam.efficientad_model_version_id = model.id
                        await cam_repo.update(cam)
                        imported[-1]["bound"] = True
                    else:
                        imported[-1]["bound"] = False
                        errors.append(f"CameraConfig 不存在: {camera_id}，PatchCore 模型未绑定")
            except Exception as exc:
                errors.append(f"注册 {patchcore_path.name} 失败: {exc}")

        # 注册 CameraNormalizer
        if norm_path:
            try:
                model_name = f"camera_normalizer_{camera_id}"
                model = await train_svc.create_model_version(
                    model_name=model_name,
                    version=version,
                    model_type="camera_normalizer",
                    artifact_path=str(norm_path.absolute()),
                )
                imported.append({
                    "camera_id": camera_id,
                    "model_type": "camera_normalizer",
                    "model_id": model.id,
                    "model_name": model_name,
                    "file": norm_path.name,
                })

                if request.auto_bind:
                    cam = await cam_repo.get_by_camera_id(request.seat_model_id, camera_id)
                    if cam:
                        cam.normalizer_model_version_id = model.id
                        await cam_repo.update(cam)
                        imported[-1]["bound"] = True
                    else:
                        imported[-1]["bound"] = False
            except Exception as exc:
                errors.append(f"注册 {norm_path.name} 失败: {exc}")

    # 注册 EmbeddingProjector（全局共享）
    if projector_path:
        try:
            model_name = "embedding_projector"
            model = await train_svc.create_model_version(
                model_name=model_name,
                version=version,
                model_type="projector",
                artifact_path=str(projector_path.absolute()),
            )
            imported.append({
                "camera_id": "global",
                "model_type": "projector",
                "model_id": model.id,
                "model_name": model_name,
                "file": projector_path.name,
            })

            if request.auto_bind and seat_model.projector_model_version_id is None:
                seat_model.projector_model_version_id = model.id
                await seat_repo.update(seat_model)
                imported[-1]["bound"] = True
            else:
                imported[-1]["bound"] = False
        except Exception as exc:
            errors.append(f"注册 projector.npz 失败: {exc}")

    await session.commit()

    return BatchTrainImportResult(
        status="completed" if not errors else "partial",
        imported=imported,
        errors=errors,
    )


def _build_timestamp_version() -> str:
    from datetime import datetime
    return datetime.utcnow().strftime("%Y%m%d%H%M%S")
