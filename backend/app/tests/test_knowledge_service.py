from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.knowledge import KnowledgeService


@pytest.mark.asyncio
async def test_create_knowledge_entry(db_session: AsyncSession) -> None:
    service = KnowledgeService(db_session)
    entry = await service.create_entry(
        category="defect",
        title="Test wrinkle pattern",
        description="A common wrinkle defect on left side",
        defect_type="wrinkle",
        action="NG",
    )
    assert entry.id is not None
    assert entry.category == "defect"
    assert entry.defect_type == "wrinkle"
    assert entry.title == "Test wrinkle pattern"
    assert entry.action == "NG"


@pytest.mark.asyncio
async def test_auto_generate_from_false_alarm_review(db_session: AsyncSession) -> None:
    service = KnowledgeService(db_session)
    entry = await service.auto_generate_from_review(
        cluster_id="cluster_abc",
        review_action="mark_false_alarm",
        defect_type=None,
    )
    assert entry is not None
    assert entry.category == "false_alarm"
    assert entry.action == "ignore"
    assert entry.cluster_id == "cluster_abc"


@pytest.mark.asyncio
async def test_auto_generate_from_defect_review(db_session: AsyncSession) -> None:
    service = KnowledgeService(db_session)
    entry = await service.auto_generate_from_review(
        cluster_id="cluster_xyz",
        review_action="confirm_defect",
        defect_type="scratch",
    )
    assert entry is not None
    assert entry.category == "defect"
    assert entry.defect_type == "scratch"
    assert entry.action == "NG"


@pytest.mark.asyncio
async def test_auto_generate_rename_review_returns_none(db_session: AsyncSession) -> None:
    service = KnowledgeService(db_session)
    entry = await service.auto_generate_from_review(
        cluster_id="cluster_def",
        review_action="rename",
        defect_type=None,
    )
    assert entry is None


@pytest.mark.asyncio
async def test_list_entries(db_session: AsyncSession) -> None:
    service = KnowledgeService(db_session)
    await service.create_entry(
        category="defect", title="Defect A", defect_type="wrinkle", action="NG"
    )
    await service.create_entry(
        category="false_alarm", title="False Alarm B", action="ignore"
    )
    await service.create_entry(
        category="camera_issue", title="Camera Issue C", action="ignore"
    )

    entries, total = await service.list_entries(offset=0, limit=10)
    assert total == 3
    assert len(entries) == 3


@pytest.mark.asyncio
async def test_search_knowledge(db_session: AsyncSession) -> None:
    service = KnowledgeService(db_session)
    await service.create_entry(
        category="defect",
        title="Unique pattern scratch",
        description="defect in corner",
        defect_type="scratch",
        action="NG",
    )
    await service.create_entry(
        category="false_alarm",
        title="Light reflection",
        description="reflection caused by overhead light",
        action="ignore",
    )

    results = await service.search("scratch", limit=10)
    assert len(results) == 1
    assert results[0].title == "Unique pattern scratch"
