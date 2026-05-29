"""数据隔离回退策略工具。

实现 3 级隔离回退：
  seat_model_id + camera_id -> seat_model_id -> global

调用方提供当前可用的隔离键和回调函数，
IsolationResolver 从最细粒度层级逐级回退，找到首个样本量 >= min_samples 的层级后返回回调结果。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Awaitable, TypeVar

from structlog import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


@dataclass(frozen=True)
class IsolationKey:
    """一组隔离键，None 表示该维度不参与过滤。"""
    seat_model_id: str | None
    camera_id: str | None

    @property
    def level_name(self) -> str:
        parts: list[str] = []
        if self.seat_model_id:
            parts.append(f"model={self.seat_model_id}")
        if self.camera_id:
            parts.append(f"camera={self.camera_id}")
        return "|".join(parts) if parts else "global"

    def fallback(self) -> IsolationKey | None:
        """返回退一级的隔离键，若已是全局则返回 None。"""
        if self.camera_id is not None:
            return IsolationKey(self.seat_model_id, None)
        if self.seat_model_id is not None:
            return IsolationKey(None, None)
        return None  # 已是全局，无法再退

    @staticmethod
    def all_levels(
        seat_model_id: str | None,
        camera_id: str | None,
    ) -> list[IsolationKey]:
        """生成从最细到最粗的所有隔离层级列表。"""
        levels: list[IsolationKey] = [
            IsolationKey(seat_model_id, camera_id),
        ]
        while True:
            fb = levels[-1].fallback()
            if fb is None:
                break
            levels.append(fb)
        return levels


class IsolationResolver:
    """按隔离层级逐级回退查询。

    用法:
        resolver = IsolationResolver(min_samples=50)
        result = await resolver.resolve(
            keys=IsolationKey.all_levels(seat_model_id, camera_id),
            query_fn=lambda key: repo.count_embeddings(key),
        )
    """

    def __init__(self, min_samples: int = 50) -> None:
        self._min_samples = min_samples

    async def resolve(
        self,
        keys: list[IsolationKey],
        count_fn: Callable[[IsolationKey], Awaitable[int]],
        action_fn: Callable[[IsolationKey], Awaitable[T]],
    ) -> T:
        """从最细粒度层级开始逐级尝试，找到首个满足样本量的层级后执行 action_fn。

        Args:
            keys: 从最细到最粗的隔离层级列表。
            count_fn: 给定 key，返回该层级当前样本量。
            action_fn: 给定 key，执行实际业务查询。

        Returns:
            action_fn 在当前最优隔离层级下的返回值。
        """
        selected: IsolationKey | None = None
        for key in keys:
            try:
                count = await count_fn(key)
            except Exception:
                logger.warning("isolation_count_failed", level=key.level_name)
                continue

            if count >= self._min_samples:
                selected = key
                logger.info(
                    "isolation_level_selected",
                    level=key.level_name,
                    sample_count=count,
                    min_samples=self._min_samples,
                )
                break
            else:
                logger.info(
                    "isolation_level_insufficient",
                    level=key.level_name,
                    sample_count=count,
                    min_samples=self._min_samples,
                )

        if selected is None:
            selected = IsolationKey(None, None)
            logger.info(
                "isolation_fallback_to_global",
                sample_count=await count_fn(selected),
                min_samples=self._min_samples,
            )

        return await action_fn(selected)
