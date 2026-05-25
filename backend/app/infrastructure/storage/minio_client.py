from __future__ import annotations

import asyncio
from datetime import timedelta
from io import BytesIO

from minio import Minio
from minio.error import S3Error

from app.core.config import settings
from app.core.exceptions import StorageError
from app.common.logging import get_logger

logger = get_logger(__name__)


class MinIOClient:
    def __init__(self) -> None:
        self._client = Minio(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self._bucket = settings.minio_bucket

    async def ensure_bucket(self) -> None:
        try:
            exists = await asyncio.to_thread(
                self._client.bucket_exists, self._bucket
            )
            if not exists:
                await asyncio.to_thread(self._client.make_bucket, self._bucket)
                logger.info("created_bucket", bucket=self._bucket)
        except S3Error as e:
            raise StorageError(f"Failed to ensure bucket: {e}") from e

    async def upload(
        self,
        object_name: str,
        data: bytes,
        content_type: str = "image/jpeg",
    ) -> str:
        try:
            result = await asyncio.to_thread(
                self._client.put_object,
                bucket_name=self._bucket,
                object_name=object_name,
                data=BytesIO(data),
                length=len(data),
                content_type=content_type,
            )
            return result.object_name
        except S3Error as e:
            logger.error("upload_failed", object_name=object_name, error=str(e))
            raise StorageError(f"Upload failed: {e}") from e

    async def download(self, object_name: str) -> bytes:
        try:
            response = await asyncio.to_thread(
                self._client.get_object,
                bucket_name=self._bucket,
                object_name=object_name,
            )
            data = await asyncio.to_thread(response.read)
            await asyncio.to_thread(response.close)
            return data
        except S3Error as e:
            raise StorageError(f"Download failed: {e}") from e

    async def delete(self, object_name: str) -> None:
        try:
            await asyncio.to_thread(
                self._client.remove_object,
                bucket_name=self._bucket,
                object_name=object_name,
            )
        except S3Error as e:
            logger.error("delete_failed", object_name=object_name, error=str(e))
            raise StorageError(f"Delete failed: {e}") from e

    async def get_presigned_url(self, object_name: str, expires_seconds: int = 3600) -> str:
        try:
            return await asyncio.to_thread(
                self._client.presigned_get_object,
                bucket_name=self._bucket,
                object_name=object_name,
                expires=timedelta(seconds=expires_seconds),
            )
        except S3Error as e:
            raise StorageError(f"Presigned URL failed: {e}") from e

    async def object_exists(self, object_name: str) -> bool:
        try:
            await asyncio.to_thread(
                self._client.stat_object, self._bucket, object_name
            )
            return True
        except S3Error:
            return False

    async def list_objects(self, prefix: str) -> list:
        """列出指定前缀下的所有对象。"""
        try:
            objects = await asyncio.to_thread(
                self._client.list_objects,
                bucket_name=self._bucket,
                prefix=prefix,
            )
            return list(objects)
        except S3Error as e:
            raise StorageError(f"List objects failed: {e}") from e


minio_client = MinIOClient()
