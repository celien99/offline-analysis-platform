from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile

from app.common.logging import get_logger
from app.core.config import settings
from app.schemas.common import StatusResponse
from app.workers.efficientad_training_worker.tasks import train_efficientad_model

router = APIRouter(prefix="/api/efficientad-training", tags=["efficientad-training"])
logger = get_logger(__name__)


@router.post("/start", response_model=StatusResponse)
async def start_efficientad_training(
    camera_id: str = Form(..., description="目标相机 ID"),
    good_images: list[UploadFile] = File(..., description="正常参考图像文件（可多张）"),
) -> StatusResponse:
    """上传正常参考图像，启动 EfficientAD 模型训练任务。

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
    tmp_dir = tempfile.mkdtemp(prefix="efficientad_images_")
    image_paths: list[str] = []

    try:
        for i, img_file in enumerate(good_images):
            content = await img_file.read()
            ext = Path(img_file.filename or f"image_{i}").suffix or ".jpg"
            save_path = str(Path(tmp_dir) / f"good_{i:04d}{ext}")
            with open(save_path, "wb") as f:
                f.write(content)
            image_paths.append(save_path)

        task = train_efficientad_model.delay(
            camera_id=camera_id,
            config_json=config_json,
            good_image_paths=image_paths,
        )

        logger.info(
            "efficientad_training_dispatched",
            task_id=task.id,
            camera_id=camera_id,
            image_count=len(image_paths),
        )
        return StatusResponse(
            status="queued",
            message=f"EfficientAD training task {task.id} dispatched",
            task_id=task.id,
        )
    except Exception as e:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise e
