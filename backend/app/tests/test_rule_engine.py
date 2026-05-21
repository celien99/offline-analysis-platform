from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.rule_engine import RuleEngineService


@pytest.mark.asyncio
async def test_create_rule(db_session: AsyncSession) -> None:
    service = RuleEngineService(db_session)
    rule = await service.create_rule(
        name="Test Ignore Reflection",
        rule_type="ignore",
        condition={"defect_type": "reflection"},
        priority=5,
    )
    assert rule.id is not None
    assert rule.name == "Test Ignore Reflection"
    assert rule.rule_type == "ignore"
    assert rule.priority == 5
    assert rule.enabled is True


@pytest.mark.asyncio
async def test_evaluate_no_rules(db_session: AsyncSession) -> None:
    service = RuleEngineService(db_session)
    result = await service.evaluate(
        camera_id="cam_test",
        defect_type="scratch",
        anomaly_score=0.85,
    )
    assert result["action"] == "flag"
    assert len(result["matched_rules"]) == 0


@pytest.mark.asyncio
async def test_evaluate_with_matching_rule(db_session: AsyncSession) -> None:
    service = RuleEngineService(db_session)
    await service.create_rule(
        name="Ignore Reflection",
        rule_type="ignore",
        condition={"defect_type": "reflection"},
        priority=5,
    )
    await service.create_rule(
        name="Flag Scratches",
        rule_type="flag",
        condition={"defect_type": "scratch", "min_score": 0.7},
        priority=10,
    )

    result = await service.evaluate(
        camera_id="cam_test",
        defect_type="scratch",
        anomaly_score=0.85,
    )
    assert result["action"] == "flag"
    assert len(result["matched_rules"]) > 0
    names = [r["name"] for r in result["matched_rules"]]
    assert "Flag Scratches" in names


@pytest.mark.asyncio
async def test_evaluate_higher_priority_wins(db_session: AsyncSession) -> None:
    service = RuleEngineService(db_session)
    await service.create_rule(
        name="Ignore All",
        rule_type="ignore",
        condition={},
        priority=100,
    )
    await service.create_rule(
        name="Flag Default",
        rule_type="flag",
        condition={},
        priority=1,
    )

    result = await service.evaluate(
        camera_id="cam_test",
        defect_type="wrinkle",
    )
    assert result["action"] == "ignore"
    assert len(result["matched_rules"]) == 2


@pytest.mark.asyncio
async def test_toggle_rule(db_session: AsyncSession) -> None:
    service = RuleEngineService(db_session)
    rule = await service.create_rule(
        name="Toggle Test",
        rule_type="flag",
        condition={},
        priority=1,
    )
    assert rule.enabled is True

    updated = await service.toggle_rule(rule.id, False)
    assert updated is not None
    assert updated.enabled is False

    updated2 = await service.toggle_rule(rule.id, True)
    assert updated2 is not None
    assert updated2.enabled is True


@pytest.mark.asyncio
async def test_condition_camera_filter(db_session: AsyncSession) -> None:
    service = RuleEngineService(db_session)
    await service.create_rule(
        name="Specific Camera Only",
        rule_type="escalate",
        condition={"camera_id": "cam_left_top"},
        priority=10,
    )

    result_match = await service.evaluate(camera_id="cam_left_top")
    assert len(result_match["matched_rules"]) == 1

    result_nomatch = await service.evaluate(camera_id="cam_right_top")
    assert len(result_nomatch["matched_rules"]) == 0
