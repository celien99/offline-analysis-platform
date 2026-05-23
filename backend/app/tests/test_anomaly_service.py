from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.anomaly import AnomalyRecord
from app.services.anomaly import AnomalyService


@pytest.fixture
def mock_minio() -> AsyncMock:
    minio = AsyncMock()
    minio.upload = AsyncMock()
    minio.get_presigned_url = AsyncMock(return_value="http://minio/presigned/url")
    return minio


@pytest.mark.asyncio
async def test_create_anomaly_with_files_basic(
    db_session: AsyncSession, mock_minio: AsyncMock,
) -> None:
    service = AnomalyService(db_session, mock_minio)
    detected = datetime(2025, 6, 15, 10, 30, tzinfo=timezone.utc)

    anomaly = await service.create_anomaly_with_files(
        camera_id="cam_01",
        source="patchcore",
        anomaly_score=0.87,
        date_folder="2025-06-15",
        detected_at=detected,
    )

    assert isinstance(anomaly, AnomalyRecord)
    assert anomaly.camera_id == "cam_01"
    assert anomaly.status == "pending"
    assert anomaly.anomaly_score == 0.87


@pytest.mark.asyncio
async def test_create_and_retrieve_anomaly(
    db_session: AsyncSession, mock_minio: AsyncMock,
) -> None:
    service = AnomalyService(db_session, mock_minio)
    detected = datetime(2025, 7, 1, tzinfo=timezone.utc)

    created = await service.create_anomaly_with_files(
        camera_id="cam_02",
        date_folder="2025-07-01",
        detected_at=detected,
    )
    retrieved = await service.get_anomaly(created.id)

    assert retrieved.id == created.id
    assert retrieved.camera_id == "cam_02"


@pytest.mark.asyncio
async def test_get_anomaly_not_found(
    db_session: AsyncSession, mock_minio: AsyncMock,
) -> None:
    service = AnomalyService(db_session, mock_minio)
    with pytest.raises(NotFoundError):
        await service.get_anomaly("nonexistent_id")


@pytest.mark.asyncio
async def test_list_anomalies(
    db_session: AsyncSession, mock_minio: AsyncMock,
) -> None:
    service = AnomalyService(db_session, mock_minio)
    dt = datetime(2025, 8, 1, tzinfo=timezone.utc)

    await service.create_anomaly_with_files(camera_id="cam_a", date_folder="2025-08-01", detected_at=dt)
    await service.create_anomaly_with_files(camera_id="cam_b", date_folder="2025-08-01", detected_at=dt)

    records, total = await service.list_anomalies(offset=0, limit=20)
    assert total >= 2
    assert len(records) >= 2


@pytest.mark.asyncio
async def test_list_anomalies_filtered(
    db_session: AsyncSession, mock_minio: AsyncMock,
) -> None:
    service = AnomalyService(db_session, mock_minio)
    dt = datetime(2025, 9, 1, tzinfo=timezone.utc)

    await service.create_anomaly_with_files(camera_id="cam_x", date_folder="2025-09-01", detected_at=dt)
    await service.create_anomaly_with_files(camera_id="cam_y", date_folder="2025-09-01", detected_at=dt)

    records, total = await service.list_anomalies(camera_id="cam_x", offset=0, limit=20)
    assert total >= 1
    assert all(r.camera_id == "cam_x" for r in records)


@pytest.mark.asyncio
async def test_reprocess_anomaly(
    db_session: AsyncSession, mock_minio: AsyncMock,
) -> None:
    service = AnomalyService(db_session, mock_minio)
    dt = datetime(2025, 10, 1, tzinfo=timezone.utc)

    created = await service.create_anomaly_with_files(
        camera_id="cam_r", date_folder="2025-10-01", detected_at=dt,
    )
    updated = await service.reprocess_anomaly(created.id)

    assert updated.status == "pending"
    assert updated.id == created.id


@pytest.mark.asyncio
async def test_create_anomaly_with_files(
    db_session: AsyncSession, mock_minio: AsyncMock,
) -> None:
    service = AnomalyService(db_session, mock_minio)
    dt = datetime(2025, 11, 1, tzinfo=timezone.utc)
    fake_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF"

    anomaly = await service.create_anomaly_with_files(
        camera_id="cam_f",
        date_folder="2025-11-01",
        detected_at=dt,
        crop_data_list=[fake_bytes],
    )

    assert anomaly.crop_path is not None
    assert anomaly.crop_paths is not None
    assert anomaly.status == "pending"
    assert mock_minio.upload.call_count == 1  # crop_0.jpg
