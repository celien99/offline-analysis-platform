from __future__ import annotations

import json
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.common.logging import get_logger
from app.core.config import settings
from app.repositories.camera_config import CameraConfigRepository, SeatModelRepository
from app.schemas.common import StatusResponse
from app.schemas.inspection import CameraInspectionResultSchema, InspectionResultResponse
from app.workers.inspection_worker.tasks import run_inspection_task

router = APIRouter(prefix="/api/inspection", tags=["inspection"])
logger = get_logger(__name__)


@router.post("/run-with-files", response_model=StatusResponse)
async def run_inspection_with_files(
    seat_model_id: str = Form(..., description="座椅型号 ID"),
    camera_ids: str = Form(..., description="逗号分隔的 camera_id 列表"),
    image_files: list[UploadFile] = File(..., description="与 camera_ids 顺序对应的图像文件"),
    part_id: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
) -> StatusResponse:
    """上传相机图像，触发检测任务。相机配置从数据库读取。"""
    camera_id_list = [cid.strip() for cid in camera_ids.split(",") if cid.strip()]

    if len(camera_id_list) != len(image_files):
        return StatusResponse(
            status="error",
            message=f"camera_ids 数量 ({len(camera_id_list)}) 与 image_files 数量 ({len(image_files)}) 不匹配",
        )

    # 从数据库读取相机配置
    seat_repo = SeatModelRepository(session)
    cam_repo = CameraConfigRepository(session)
    seat_model = await seat_repo.get_by_seat_model_id(seat_model_id)
    if not seat_model:
        return StatusResponse(status="error", message=f"座椅型号不存在: {seat_model_id}")

    # 验证所有 camera_id 都有配置
    cameras = await cam_repo.list_by_seat_model(seat_model_id)
    db_camera_ids = {c.camera_id for c in cameras}
    for cid in camera_id_list:
        if cid not in db_camera_ids:
            return StatusResponse(
                status="error",
                message=f"相机 {cid} 在座椅型号 {seat_model_id} 下无配置",
            )

    # 收集所有用到的 model_version_id，查询 artifact_path
    model_version_ids: set[str] = set()
    for c in cameras:
        for mv_id in (
            c.patchcore_model_version_id,
            c.yolo_model_version_id,
            c.region_upper_model_version_id,
            c.region_middle_model_version_id,
            c.region_lower_model_version_id,
        ):
            if mv_id:
                model_version_ids.add(mv_id)

    model_paths: dict[str, str] = {}
    if model_version_ids:
        from app.models.registry import ModelVersion
        from sqlalchemy import select

        mv_stmt = select(ModelVersion).where(ModelVersion.id.in_(model_version_ids))
        mv_result = await session.execute(mv_stmt)
        for mv in mv_result.scalars().all():
            model_paths[mv.id] = mv.artifact_path

    # 生成完整配置文件
    from app.services.camera_config.builder import ConfigBuilder

    builder = ConfigBuilder()
    config_dict = builder.build(
        seat_model_id=seat_model_id,
        display_name=seat_model.display_name,
        cameras=cameras,
        model_paths=model_paths,
        selected_camera_ids=camera_id_list,
        upload_base_url=settings.backend_base_url,
    )

    # 保存图像到临时目录
    tmp_dir = tempfile.mkdtemp(prefix="inspection_images_")
    camera_image_paths: dict[str, str] = {}

    try:
        # 将配置写入临时文件
        config_path = str(Path(tmp_dir) / "config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, ensure_ascii=False, indent=2)

        for i, (camera_id, img_file) in enumerate(zip(camera_id_list, image_files)):
            content = await img_file.read()
            ext = Path(img_file.filename or f"image_{i}").suffix or ".jpg"
            save_path = str(Path(tmp_dir) / f"{camera_id}{ext}")
            with open(save_path, "wb") as f:
                f.write(content)
            camera_image_paths[camera_id] = save_path

        task = run_inspection_task.delay(
            config_path=config_path,
            camera_image_paths=camera_image_paths,
            seat_model_id=seat_model_id,
            part_id=part_id,
        )

        logger.info(
            "inspection_dispatched",
            task_id=task.id,
            seat_model_id=seat_model_id,
            camera_count=len(camera_id_list),
        )
        return StatusResponse(
            status="queued",
            message=f"Inspection task {task.id} dispatched",
            task_id=task.id,
        )
    except Exception as e:
        import shutil

        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise e


@router.get("/result/{task_id}", response_model=InspectionResultResponse)
async def get_inspection_result(
    task_id: str,
) -> InspectionResultResponse:
    """查询检测任务结果。"""
    from celery.result import AsyncResult

    from app.infrastructure.queue.celery_app import celery_app

    result = AsyncResult(task_id, app=celery_app)
    info = result.result if result.ready() and result.result else {}

    response = InspectionResultResponse(
        task_id=task_id,
        status=result.state if result.state else "PENDING",
    )

    if isinstance(info, dict):
        response.overall_status = info.get("overall_status")
        response.decision_reason = info.get("decision_reason")
        response.error_message = info.get("error_message")
        camera_results = info.get("camera_results", [])
        response.camera_results = [
            CameraInspectionResultSchema(**cr) if isinstance(cr, dict) else cr
            for cr in camera_results
        ]

    return response
