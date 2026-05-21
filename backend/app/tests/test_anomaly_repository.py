from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.anomaly import AnomalyRecord
from app.repositories.anomaly.repository import AnomalyRepository


@pytest.mark.asyncio
async def test_create_anomaly(db_session: AsyncSession) -> None:
    repo = AnomalyRepository(db_session)
    anomaly = AnomalyRecord(
        id="test001",
        camera_id="cam_left_top",
        source="patchcore",
        anomaly_score=0.85,
        date_folder="2026-05-20",
        detected_at=datetime.now(tz=timezone.utc),
        status="pending",
    )
    created = await repo.create(anomaly)
    assert created.id == "test001"
    assert created.camera_id == "cam_left_top"


@pytest.mark.asyncio
async def test_get_by_id(db_session: AsyncSession) -> None:
    repo = AnomalyRepository(db_session)
    anomaly = AnomalyRecord(
        id="test002",
        camera_id="cam_right_top",
        source="filter_classifier",
        anomaly_score=0.92,
        date_folder="2026-05-20",
        detected_at=datetime.now(tz=timezone.utc),
        status="pending",
    )
    await repo.create(anomaly)

    found = await repo.get_by_id("test002")
    assert found is not None
    assert found.camera_id == "cam_right_top"


@pytest.mark.asyncio
async def test_get_by_id_not_found(db_session: AsyncSession) -> None:
    repo = AnomalyRepository(db_session)
    found = await repo.get_by_id("nonexistent")
    assert found is None


@pytest.mark.asyncio
async def test_update_status(db_session: AsyncSession) -> None:
    repo = AnomalyRepository(db_session)
    anomaly = AnomalyRecord(
        id="test003",
        camera_id="cam_front",
        source="patchcore",
        anomaly_score=0.75,
        date_folder="2026-05-20",
        detected_at=datetime.now(tz=timezone.utc),
        status="pending",
    )
    await repo.create(anomaly)

    await repo.update_status("test003", "embedded")
    updated = await repo.get_by_id("test003")
    assert updated is not None
    assert updated.status == "embedded"
