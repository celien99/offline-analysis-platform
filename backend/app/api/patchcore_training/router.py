from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile

from app.common.logging import get_logger
from app.core.config import settings
from app.schemas.common import StatusResponse
from app.workers.patchcore_training_worker.tasks import train_patchcore_model

router = APIRouter(prefix="/api/patchcore-training", tags=["patchcore-training"])
logger = get_logger(__name__)


@router.post("/start", response_model=StatusResponse)
async def start_patchcore_training(
    camera_id: str = Form(..., description="目标相机 ID"),
    region_id: str | None = Form(default=None, description="可选 ROI 区域 ID"),
    input_mode: str = Form(default="roi", pattern="^(roi|online)$", description="训练输入模式"),
    good_images: list[UploadFile] = File(..., description="正常参考图像文件（可多张）"),
) -> StatusResponse:
    """上传正常参考图像，启动 PatchCore 模型训练任务。

    训练参数从内置配置文件（INDUSTRIAL_DEFAULT_INSPECTION_CONFIG）中读取，
    用户仅需提供目标相机 ID 和正常参考图像。
    """
    # 从内置配置读取 JSON 内容
    config_path = Path(settings.default_inspection_config)
    if not config_path.exists():
        return StatusResponse(
            status="error",
            message=f"默认配置文件不存在: {settings.default_inspection_config}",
        )
    config_json = config_path.read_text(encoding="utf-8")

    # 将上传的图片保存到临时目录
    tmp_dir = tempfile.mkdtemp(prefix="patchcore_images_")
    image_paths: list[str] = []

    try:
        for i, img_file in enumerate(good_images):
            content = await img_file.read()
            ext = Path(img_file.filename or f"image_{i}").suffix or ".jpg"
            save_path = str(Path(tmp_dir) / f"good_{i:04d}{ext}")
            with open(save_path, "wb") as f:
                f.write(content)
            image_paths.append(save_path)

        task = train_patchcore_model.delay(
            camera_id=camera_id,
            config_json=config_json,
            good_image_paths=image_paths,
            input_mode=input_mode,
            region_id=region_id,
        )

        logger.info(
            "patchcore_training_dispatched",
            task_id=task.id,
            camera_id=camera_id,
            region_id=region_id,
            input_mode=input_mode,
            image_count=len(image_paths),
        )
        return StatusResponse(
            status="queued",
            message=f"PatchCore training task {task.id} dispatched",
            task_id=task.id,
        )
    except Exception as e:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise e
