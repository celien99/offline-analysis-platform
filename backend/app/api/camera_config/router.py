from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.models.camera_config import SeatModel
from app.models.registry import ModelVersion
from app.repositories.camera_config import CameraConfigRepository, SeatModelRepository
from app.schemas.camera_config import (
    CameraConfigCreate,
    CameraConfigResponse,
    CameraConfigUpdate,
    CameraOption,
    SeatModelCreate,
    SeatModelOption,
    SeatModelResponse,
    SeatModelUpdate,
)

router = APIRouter(prefix="/api/seat-models", tags=["camera-config"])


# ── Seat Models CRUD ──


@router.get("/options", response_model=list[SeatModelOption])
async def list_seat_model_options(
    session: AsyncSession = Depends(get_session),
) -> list[SeatModelOption]:
    """获取所有座椅型号及关联相机，供检测页面下拉框使用。"""
    seat_repo = SeatModelRepository(session)
    cam_repo = CameraConfigRepository(session)
    seat_models = await seat_repo.list_with_cameras()
    result: list[SeatModelOption] = []
    for sm in seat_models:
        cameras = await cam_repo.list_by_seat_model(sm.seat_model_id)
        result.append(
            SeatModelOption(
                seat_model_id=sm.seat_model_id,
                display_name=sm.display_name,
                cameras=[
                    CameraOption(camera_id=c.camera_id)
                    for c in cameras
                ],
            )
        )
    return result


@router.get("", response_model=list[SeatModelResponse])
async def list_seat_models(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> list[SeatModelResponse]:
    seat_repo = SeatModelRepository(session)
    offset = (page - 1) * page_size
    models = await seat_repo.list_all(offset=offset, limit=page_size)
    return [SeatModelResponse.model_validate(m) for m in models]


@router.post("", response_model=SeatModelResponse, status_code=201)
async def create_seat_model(
    data: SeatModelCreate,
    session: AsyncSession = Depends(get_session),
) -> SeatModelResponse:
    seat_repo = SeatModelRepository(session)
    existing = await seat_repo.get_by_seat_model_id(data.seat_model_id)
    if existing:
        raise HTTPException(status_code=409, detail="seat_model_id 已存在")

    entity = SeatModel(
        seat_model_id=data.seat_model_id,
        display_name=data.display_name,
        yolo_model_version_id=data.yolo_model_version_id,
        projector_model_version_id=data.projector_model_version_id,
        whitening_matrix_model_version_id=data.whitening_matrix_model_version_id,
    )
    await seat_repo.create(entity)
    await session.commit()
    return SeatModelResponse.model_validate(entity)


@router.put("/{seat_model_db_id}", response_model=SeatModelResponse)
async def update_seat_model(
    seat_model_db_id: str,
    data: SeatModelUpdate,
    session: AsyncSession = Depends(get_session),
) -> SeatModelResponse:
    seat_repo = SeatModelRepository(session)
    entity = await seat_repo.get_by_id(seat_model_db_id)
    if not entity:
        raise HTTPException(status_code=404, detail="座椅型号不存在")
    if data.seat_model_id is not None:
        entity.seat_model_id = data.seat_model_id
    if data.display_name is not None:
        entity.display_name = data.display_name
    if data.yolo_model_version_id is not None:
        entity.yolo_model_version_id = data.yolo_model_version_id
    if data.projector_model_version_id is not None:
        entity.projector_model_version_id = data.projector_model_version_id
    if data.whitening_matrix_model_version_id is not None:
        entity.whitening_matrix_model_version_id = data.whitening_matrix_model_version_id
    await seat_repo.update(entity)
    await session.commit()
    return SeatModelResponse.model_validate(entity)


@router.delete("/{seat_model_db_id}", status_code=204)
async def delete_seat_model(
    seat_model_db_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    seat_repo = SeatModelRepository(session)
    entity = await seat_repo.get_by_id(seat_model_db_id)
    if not entity:
        raise HTTPException(status_code=404, detail="座椅型号不存在")
    await seat_repo.soft_delete(seat_model_db_id)
    await session.commit()
    return None


# ── Camera Config CRUD ──


@router.get(
    "/{seat_model_id}/cameras",
    response_model=list[CameraConfigResponse],
)
async def list_cameras(
    seat_model_id: str,
    session: AsyncSession = Depends(get_session),
) -> list[CameraConfigResponse]:
    cam_repo = CameraConfigRepository(session)
    cameras = await cam_repo.list_by_seat_model(seat_model_id)
    return [CameraConfigResponse.model_validate(c) for c in cameras]


@router.post(
    "/{seat_model_id}/cameras",
    response_model=CameraConfigResponse,
    status_code=201,
)
async def create_camera(
    seat_model_id: str,
    data: CameraConfigCreate,
    session: AsyncSession = Depends(get_session),
) -> CameraConfigResponse:
    seat_repo = SeatModelRepository(session)
    seat_model = await seat_repo.get_by_seat_model_id(seat_model_id)
    if not seat_model:
        raise HTTPException(status_code=404, detail="座椅型号不存在")

    cam_repo = CameraConfigRepository(session)
    existing = await cam_repo.get_by_camera_id(seat_model_id, data.camera_id)
    if existing:
        raise HTTPException(status_code=409, detail="同一座椅型号下 camera_id 已存在")

    from app.models.camera_config import CameraConfig

    await _validate_patchcore_model_bindings(
        session,
        data.efficientad_model_version_id,
        data.regions,
    )
    payload = data.model_dump(exclude={"regions"})
    entity = CameraConfig(
        seat_model_id=seat_model_id,
        **payload,
    )
    await cam_repo.create(entity)
    await cam_repo.replace_regions(
        entity,
        _build_region_binding_entities(data.regions),
    )
    await session.commit()
    return CameraConfigResponse.model_validate(entity)


@router.put(
    "/{seat_model_id}/cameras/{camera_db_id}",
    response_model=CameraConfigResponse,
)
async def update_camera(
    seat_model_id: str,
    camera_db_id: str,
    data: CameraConfigUpdate,
    session: AsyncSession = Depends(get_session),
) -> CameraConfigResponse:
    cam_repo = CameraConfigRepository(session)
    entity = await cam_repo.get_by_id(camera_db_id)
    if not entity:
        raise HTTPException(status_code=404, detail="相机配置不存在")

    update_data = data.model_dump(exclude_unset=True)
    regions = update_data.pop("regions", None)
    patchcore_model_version_id = update_data.get(
        "efficientad_model_version_id",
        entity.efficientad_model_version_id,
    )
    if data.efficientad_model_version_id is not None or regions is not None:
        region_bindings = regions if regions is not None else entity.regions
        await _validate_patchcore_model_bindings(
            session,
            patchcore_model_version_id,
            region_bindings,
        )
    for key, value in update_data.items():
        setattr(entity, key, value)
    if regions is not None:
        await cam_repo.replace_regions(
            entity,
            _build_region_binding_entities(regions),
        )
    await cam_repo.update(entity)
    await session.commit()
    return CameraConfigResponse.model_validate(entity)


@router.delete("/{seat_model_id}/cameras/{camera_db_id}", status_code=204)
async def delete_camera(
    seat_model_id: str,
    camera_db_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    cam_repo = CameraConfigRepository(session)
    entity = await cam_repo.get_by_id(camera_db_id)
    if not entity:
        raise HTTPException(status_code=404, detail="相机配置不存在")
    await cam_repo.soft_delete(camera_db_id)
    await session.commit()
    return None


async def _validate_patchcore_model_bindings(
    session: AsyncSession,
    camera_model_version_id: str | None,
    regions: list[dict] | list,
) -> None:
    model_ids = {camera_model_version_id} if camera_model_version_id else set()
    for raw_region in regions:
        region = (
            raw_region
            if isinstance(raw_region, dict)
            else raw_region.model_dump()
        )
        model_id = region.get("patchcore_model_version_id")
        if model_id:
            model_ids.add(model_id)

    if not model_ids:
        return

    result = await session.execute(
        select(ModelVersion).where(
            ModelVersion.deleted_at.is_(None),
            ModelVersion.id.in_(model_ids),
        )
    )
    models = {model.id: model for model in result.scalars().all()}

    missing_ids = sorted(model_ids - set(models))
    if missing_ids:
        raise HTTPException(
            status_code=400,
            detail=f"PatchCore 模型版本不存在: {', '.join(missing_ids)}",
        )

    invalid_type_ids = sorted(
        model_id
        for model_id, model in models.items()
        if model.model_type != "patchcore"
    )
    if invalid_type_ids:
        raise HTTPException(
            status_code=400,
            detail=f"请选择 PatchCore 类型模型: {', '.join(invalid_type_ids)}",
        )

    missing_paths = [
        f"{model.id} ({model.artifact_path})"
        for model in models.values()
        if not Path(model.artifact_path).is_file()
    ]
    if missing_paths:
        raise HTTPException(
            status_code=400,
            detail=f"PatchCore 模型文件不存在: {', '.join(sorted(missing_paths))}",
        )


def _build_region_binding_entities(regions: list[dict] | list) -> list:
    from app.models.camera_config import CameraConfigRegion

    entities = []
    for index, raw_region in enumerate(regions):
        region = (
            raw_region
            if isinstance(raw_region, dict)
            else raw_region.model_dump()
        )
        region_id = region["region_id"]
        entities.append(
            CameraConfigRegion(
                region_id=region_id,
                x1=0.0,
                y1=0.0,
                x2=1.0,
                y2=1.0,
                patchcore_model_version_id=region["patchcore_model_version_id"],
                enabled=True,
                sort_order=index,
                patchcore_overrides_json=None,
            )
        )
    return entities
