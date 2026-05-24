from __future__ import annotations

import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.logging import get_logger
from app.core.security import generate_uuid
from app.models.knowledge import RuleEntry
from app.repositories.knowledge import RuleRepository

logger = get_logger(__name__)


class RuleEngineService:
    """Evaluate rules against anomalies for the Rule Engine in the online pipeline.

    The Rule Engine sits after the Filter Classifier in the online system.
    Rules are derived from the offline knowledge base and pushed to online.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = RuleRepository(session)

    async def evaluate(
        self,
        *,
        camera_id: str,
        defect_type: str | None = None,
        anomaly_score: float | None = None,
        classifier_prediction: str | None = None,
    ) -> dict[str, object]:
        """Evaluate all matching rules and return the combined verdict.

        Returns:
            dict with action (ignore/flag/escalate), matched_rules, final_score
        """
        applicable = await self._repo.get_by_camera(camera_id)
        matched: list[dict[str, object]] = []
        final_action = "flag"

        for rule in applicable:
            condition = json.loads(rule.condition_json or "{}")
            if self._match_condition(
                condition,
                camera_id=camera_id,
                defect_type=defect_type,
                anomaly_score=anomaly_score,
                classifier_prediction=classifier_prediction,
            ):
                matched.append({
                    "rule_id": rule.id,
                    "name": rule.name,
                    "type": rule.rule_type,
                    "priority": rule.priority,
                })
                if rule.priority > self._get_rule_priority(final_action):
                    final_action = rule.rule_type

        logger.info(
            "rule_engine_evaluated",
            camera_id=camera_id,
            matched_count=len(matched),
            final_action=final_action,
        )

        return {
            "action": final_action,
            "matched_rules": matched,
            "rule_count": len(matched),
        }

    @staticmethod
    def _match_condition(
        condition: dict[str, object],
        *,
        camera_id: str,
        defect_type: str | None,
        anomaly_score: float | None,
        classifier_prediction: str | None,
    ) -> bool:
        if condition.get("camera_id") and condition["camera_id"] != camera_id:
            return False
        if condition.get("defect_type") and condition["defect_type"] != defect_type:
            return False
        if condition.get("min_score") and anomaly_score is not None:
            if anomaly_score < float(condition["min_score"]):
                return False
        if condition.get("max_score") and anomaly_score is not None:
            if anomaly_score > float(condition["max_score"]):
                return False
        if condition.get("classifier_prediction") and classifier_prediction != condition["classifier_prediction"]:
            return False
        return True

    @staticmethod
    def _get_rule_priority(action: str) -> int:
        return {"ignore": 1, "flag": 2, "escalate": 3}.get(action, 0)

    async def create_rule(
        self,
        *,
        name: str,
        rule_type: str,
        condition: dict[str, object],
        priority: int = 0,
        enabled: bool = True,
        camera_ids: list[str] | None = None,
        knowledge_entry_id: str | None = None,
        description: str | None = None,
    ) -> RuleEntry:
        rule = RuleEntry(
            id=generate_uuid(),
            name=name,
            rule_type=rule_type,
            condition_json=json.dumps(condition),
            priority=priority,
            enabled=enabled,
            camera_ids=json.dumps(camera_ids) if camera_ids else None,
            knowledge_entry_id=knowledge_entry_id,
            description=description,
        )
        result = await self._repo.create(rule)
        logger.info("rule_created", rule_id=result.id, name=name, type=rule_type)
        return result

    async def auto_generate_rules_from_knowledge(
        self,
        knowledge_entry_id: str,
        camera_ids: list[str] | None = None,
    ) -> list[RuleEntry]:
        """从 knowledge base entry 自动生成规则。

        生成的条件同时包含：
        - defect_type（为未来多分类 Filter Classifier 预留，当前在线端不会匹配）
        - require_filter_real_defect / require_filter_false_alarm（当前在线端可用）
        """
        from app.repositories.knowledge import KnowledgeRepository
        knowledge_repo = KnowledgeRepository(self._session)
        entry = await knowledge_repo.get_by_id(knowledge_entry_id)
        if entry is None:
            return []

        rules: list[RuleEntry] = []
        # 基础条件：defect_type 为未来多分类 FC 预留
        condition: dict[str, object] = {}
        if entry.defect_type:
            condition["defect_type"] = entry.defect_type

        if entry.action == "ignore":
            # 误报忽略：要求 FC 也判定为误报时才抑制
            condition["require_filter_false_alarm"] = True
            rules.append(await self.create_rule(
                name=f"Auto: Ignore {entry.defect_type or 'pattern'} from KB {knowledge_entry_id[:8]}",
                rule_type="ignore",
                condition=condition,
                priority=5,
                camera_ids=camera_ids or (json.loads(entry.camera_ids) if entry.camera_ids else None),
                knowledge_entry_id=knowledge_entry_id,
                description=entry.description,
            ))
        elif entry.action == "NG":
            # 真实缺陷升级：要求 FC 也判定为真实缺陷时才升级
            condition["require_filter_real_defect"] = True
            rules.append(await self.create_rule(
                name=f"Auto: Escalate {entry.defect_type or 'pattern'} from KB {knowledge_entry_id[:8]}",
                rule_type="escalate",
                condition=condition,
                priority=10,
                camera_ids=camera_ids or (json.loads(entry.camera_ids) if entry.camera_ids else None),
                knowledge_entry_id=knowledge_entry_id,
                description=entry.description,
            ))
        elif entry.action == "review_required":
            condition["require_filter_real_defect"] = True
            rules.append(await self.create_rule(
                name=f"Auto: Flag {entry.defect_type or 'pattern'} from KB {knowledge_entry_id[:8]}",
                rule_type="flag",
                condition=condition,
                priority=7,
                camera_ids=camera_ids or (json.loads(entry.camera_ids) if entry.camera_ids else None),
                knowledge_entry_id=knowledge_entry_id,
                description=entry.description,
            ))

        return rules

    async def list_rules(
        self,
        *,
        rule_type: str | None = None,
        enabled: bool | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[RuleEntry], int]:
        if enabled is not None:
            if enabled:
                rules = await self._repo.get_enabled_rules()
            else:
                rules = await self._repo.get_disabled_rules()
            total = len(rules)
            rules = rules[offset:offset + limit]
            return list(rules), total
        if rule_type:
            rules = await self._repo.get_by_type(rule_type)
            total = len(rules)
            rules = rules[offset:offset + limit]
            return list(rules), total
        rules = await self._repo.list_all(offset=offset, limit=limit)
        total = await self._repo.count()
        return list(rules), total

    async def get_rule(self, rule_id: str) -> RuleEntry | None:
        return await self._repo.get_by_id(rule_id)

    async def toggle_rule(self, rule_id: str, enabled: bool) -> RuleEntry | None:
        rule = await self._repo.get_by_id(rule_id)
        if rule is None:
            return None
        rule.enabled = enabled
        await self._repo.update(rule)
        return rule

    async def delete_rule(self, rule_id: str) -> None:
        await self._repo.soft_delete(rule_id)
