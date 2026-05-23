"""参照图管理 API：每机位可上传一张 OK 标准图，供 VLM 对比分析。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.deps import get_minio
from app.common.logging import get_logger
from app.infrastructure.storage.minio_client import MinIOClient

router = APIRouter(prefix="/api/reference", tags=["reference"])
logger = get_logger(__name__)

REFERENCE_PREFIX = "reference"


@router.post("/upload")
async def upload_reference_image(
    camera_id: str = Form(..., description="机位 ID，如 cam_front"),
    image_file: UploadFile = File(...),
    minio: MinIOClient = Depends(get_minio),
) -> dict[str, str]:
    """上传某机位的 OK 参照图。每个机位只保留最新一张。"""
    ext = ".jpg"
    if image_file.filename and "." in image_file.filename:
        ext = image_file.filename.rsplit(".", 1)[-1]
        ext = f".{ext}"
    path = f"{REFERENCE_PREFIX}/{camera_id}/ok{ext}"
    data = await image_file.read()
    content_type = image_file.content_type or "image/jpeg"
    await minio.upload(path, data, content_type)
    logger.info("reference_uploaded", camera_id=camera_id, path=path)
    return {"status": "ok", "camera_id": camera_id, "path": path}


@router.get("/list")
async def list_references(
    minio: MinIOClient = Depends(get_minio),
) -> list[dict[str, str]]:
    """列出所有已上传参照图的机位。"""
    objects = await minio.list_objects(REFERENCE_PREFIX)
    cameras: set[str] = set()
    for obj in objects:
        # obj is like "reference/cam_front/ok.jpg"
        parts = obj.object_name.split("/")
        if len(parts) >= 2:
            cameras.add(parts[1])
    return [{"camera_id": c} for c in sorted(cameras)]


@router.get("/{camera_id}")
async def get_reference_url(
    camera_id: str,
    minio: MinIOClient = Depends(get_minio),
) -> dict[str, str | None]:
    """获取某机位 OK 参照图的 presigned URL。"""
    objects = await minio.list_objects(f"{REFERENCE_PREFIX}/{camera_id}/")
    if not objects:
        return {"camera_id": camera_id, "url": None}
    path = objects[0].object_name
    url = await minio.get_presigned_url(path, expires_seconds=3600)
    return {"camera_id": camera_id, "url": url}
