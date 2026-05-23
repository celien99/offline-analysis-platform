from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile

from app.common.logging import get_logger
from app.core.config import settings
from app.schemas.common import StatusResponse
from app.schemas.inspection import CameraInspectionResultSchema, InspectionResultResponse
from app.workers.inspection_worker.tasks import run_inspection_task

router = APIRouter(prefix="/api/inspection", tags=["inspection"])
logger = get_logger(__name__)


@router.post("/run-with-files", response_model=StatusResponse)
async def run_inspection_with_files(
    seat_model_id: str | None = Form(None),
    part_id: str | None = Form(None),
    camera_ids: str = Form(..., description="逗号分隔的 camera_id 列表"),
    image_files: list[UploadFile] = File(..., description="与 camera_ids 顺序对应的图像文件"),
) -> StatusResponse:
    """上传相机图像，触发检测任务。

    检测配置从内置配置文件（INDUSTRIAL_DEFAULT_INSPECTION_CONFIG）读取，
    用户仅需提供 camera_id 及其对应的图像文件。
    """
    camera_id_list = [cid.strip() for cid in camera_ids.split(",") if cid.strip()]

    if len(camera_id_list) != len(image_files):
        return StatusResponse(
            status="error",
            message=f"camera_ids 数量 ({len(camera_id_list)}) 与 image_files 数量 ({len(image_files)}) 不匹配",
        )

    # 解析配置文件绝对路径（确保子进程可从仓库根目录找到）
    config_path = Path(settings.default_inspection_config).resolve()
    if not config_path.exists():
        return StatusResponse(
            status="error",
            message=f"默认配置文件不存在: {config_path}",
        )

    # 将图像保存到临时目录
    tmp_dir = tempfile.mkdtemp(prefix="inspection_images_")
    camera_image_paths: dict[str, str] = {}

    try:
        for i, (camera_id, img_file) in enumerate(zip(camera_id_list, image_files)):
            content = await img_file.read()
            ext = Path(img_file.filename or f"image_{i}").suffix or ".jpg"
            save_path = str(Path(tmp_dir) / f"{camera_id}{ext}")
            with open(save_path, "wb") as f:
                f.write(content)
            camera_image_paths[camera_id] = save_path

        task = run_inspection_task.delay(
            config_path=str(config_path),
            camera_image_paths=camera_image_paths,
            seat_model_id=seat_model_id,
            part_id=part_id,
        )

        logger.info(
            "inspection_dispatched",
            task_id=task.id,
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
