from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.session import get_db
from app.infrastructure.storage.minio_client import MinIOClient, minio_client


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db():
        yield session


def get_minio() -> MinIOClient:
    return minio_client
