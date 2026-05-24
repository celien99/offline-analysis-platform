"""规则部署服务：将离线平台生成的规则导出为 JSON 并部署到在线系统目录。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.logging import get_logger
from app.core.config import settings
from app.repositories.knowledge import RuleRepository

logger = get_logger(__name__)


class RuleDeploymentService:
    """将启用的规则导出为 JSON 并部署到目标目录。

    在线系统（seat_defect_core）通过 RuleEngineConfig.deployed_rules_path
    加载此 JSON 文件，与本地规则合并后参与决策。
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = RuleRepository(session)

    async def export_rules_json(self) -> list[dict[str, Any]]:
        """导出所有启用规则为 JSON 兼容的 dict 列表。"""
        rules = await self._repo.get_enabled_rules()
        result: list[dict[str, Any]] = []
        for rule in rules:
            condition = json.loads(rule.condition_json or "{}")
            camera_ids: list[str] | None = (
                json.loads(rule.camera_ids) if rule.camera_ids else None
            )

            # 离线 rule_type 到在线 action 的映射
            action_map = {
                "ignore": "ignore",
                "flag": "flag_for_review",
                "escalate": "escalate",
            }

            # 如果规则限定具体机位，为每个机位生成一条规则（方便在线直接匹配）
            target_cameras = camera_ids if camera_ids else [None]
            for cam_id in target_cameras:
                result.append({
                    "name": rule.name,
                    "enabled": rule.enabled,
                    "camera_id": cam_id,
                    "defect_type": condition.get("defect_type"),
                    "min_classifier_confidence": condition.get("min_confidence"),
                    "max_classifier_confidence": condition.get("max_confidence"),
                    "max_anomaly_score": condition.get("max_score"),
                    "require_filter_false_alarm": bool(condition.get("require_filter_false_alarm")),
                    "require_filter_real_defect": bool(condition.get("require_filter_real_defect")),
                    "action": action_map.get(rule.rule_type, "flag_for_review"),
                    "source": "offline_platform",
                    "knowledge_entry_id": rule.knowledge_entry_id,
                    "priority": rule.priority,
                })
        return result

    async def deploy_to_target(self, target: str) -> str:
        """导出规则并部署到目标目录。

        Returns:
            部署文件的绝对路径。
        """
        target_root = settings.deploy_targets.get(target)
        if target_root is None:
            raise ValueError(
                f"未知部署目标: {target}。已配置目标: {list(settings.deploy_targets.keys())}"
            )

        rules_json = await self.export_rules_json()
        target_dir = Path(target_root) / settings.deploy_rules_subdir
        target_dir.mkdir(parents=True, exist_ok=True)

        dest = target_dir / "rules.json"
        tmp_dest = target_dir / ".rules.json.tmp"

        # 原子写入：先写临时文件再 rename，避免在线系统读到不完整文件
        tmp_dest.write_text(
            json.dumps(rules_json, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_dest.rename(dest)

        logger.info(
            "rules_deployed",
            target=target,
            rule_count=len(rules_json),
            destination=str(dest),
        )
        return str(dest.resolve())
