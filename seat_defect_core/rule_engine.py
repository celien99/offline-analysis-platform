"""轻量级规则引擎，在 Filter Classifier 之后、Fusion 之前执行。

支持基于阈值的误报过滤规则，每条规则包含条件（condition）和动作（action）。
所有规则按顺序执行，命中即停止。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .types import CameraInspectionResult


@dataclass
class RuleConfig:
    """单条规则配置。"""

    name: str
    """规则名称，用于调试和日志。"""

    enabled: bool = True
    """是否启用。"""

    # 条件字段（均为可选，非空时作为阈值条件）
    max_anomaly_score: Optional[float] = None
    """异常分数低于此值触发。"""

    min_strong_patch_count: Optional[int] = None
    """强异常 patch 数低于此值触发。"""

    max_strong_patch_ratio: Optional[float] = None
    """强异常 patch 比例低于此值触发。"""

    require_filter_false_alarm: bool = False
    """要求 Filter Classifier 也将此判定为误报。"""

    # 动作
    action: str = "suppress_to_ok"
    """命中规则后的动作：suppress_to_ok / flag_for_review。"""


@dataclass
class RuleEngineConfig:
    """规则引擎配置。"""

    enabled: bool = False
    rules: List[RuleConfig] = field(default_factory=list)


def apply_rules(
    result: CameraInspectionResult,
    rules: List[RuleConfig],
) -> CameraInspectionResult:
    """对单机位检测结果依次应用规则。

    返回可能被修改的 CameraInspectionResult（原地修改 status/reason）。
    """
    if result.status != "NG":
        return result

    for rule in rules:
        if not rule.enabled:
            continue
        if _rule_matches(result, rule):
            if rule.action == "suppress_to_ok":
                result.status = "OK"
                result.reason = f"rule_{rule.name}"
            elif rule.action == "flag_for_review":
                # 保持 NG 但修改 reason 以便审核
                result.reason = f"ng_flagged_{rule.name}"
            break  # 命中即停止

    return result


def _rule_matches(result: CameraInspectionResult, rule: RuleConfig) -> bool:
    """检查检测结果是否匹配规则的所有条件。"""
    texture = result.texture_result

    # 需要 Filter Classifier 也判定为误报
    if rule.require_filter_false_alarm:
        if result.filter_result is None or result.filter_result.is_real_defect:
            return False

    # 异常分数低于阈值
    if rule.max_anomaly_score is not None:
        if texture is None or texture.score >= rule.max_anomaly_score:
            return False

    # 强异常 patch 数低于阈值
    if rule.min_strong_patch_count is not None:
        if texture is None or texture.strong_patch_count >= rule.min_strong_patch_count:
            return False

    # 强异常 patch 比例低于阈值
    if rule.max_strong_patch_ratio is not None:
        if texture is None or texture.strong_patch_ratio >= rule.max_strong_patch_ratio:
            return False

    return True


__all__ = [
    "RuleConfig",
    "RuleEngineConfig",
    "apply_rules",
]
