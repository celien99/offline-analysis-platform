from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .config import BudgetConfig, BudgetScope


@dataclass
class BudgetState:
    """Mutable state tracked across frames for budget control."""
    multiplier: float = 1.5
    recent_cc_counts: list[int] = field(default_factory=list)
    recent_latencies_ms: list[float] = field(default_factory=list)
    emergency_count: int = 0


class BudgetController:
    """Adaptive budget controller with three-mode operation."""

    def __init__(self, config: BudgetConfig | None = None):
        self.config = config or BudgetConfig()
        self._state = BudgetState()
        self._frame_start: float = 0.0

    def start_frame(self) -> None:
        self._frame_start = time.perf_counter()

    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self._frame_start) * 1000.0

    def remaining_budget_ms(self) -> float:
        return max(0.0, self.config.target_latency_ms - self.elapsed_ms())

    def regulate(self, heatmap: np.ndarray) -> tuple[float, int, str]:
        """Determine adaptive threshold and K limit for this frame.
        Returns: (threshold_value, max_proposals, mode_string)
        """
        cfg = self.config
        if not cfg.enabled:
            return (0.0, 999, "disabled")

        elapsed = self.elapsed_ms()
        self._state.recent_latencies_ms.append(elapsed)
        if len(self._state.recent_latencies_ms) > cfg.window_size:
            self._state.recent_latencies_ms.pop(0)

        # Emergency check
        cc_estimate = self._estimate_cc_count(heatmap)
        if elapsed >= cfg.hard_limit_ms or cc_estimate >= cfg.max_cc_before_emergency:
            self._state.emergency_count += 1
            return (0.99, 0, "emergency")

        # Optimization: slow adjustment based on history
        if len(self._state.recent_cc_counts) >= cfg.window_size:
            avg_cc = sum(self._state.recent_cc_counts[-cfg.window_size:]) / cfg.window_size
            if avg_cc > 20:
                self._state.multiplier = min(
                    cfg.threshold_multiplier_max,
                    self._state.multiplier + cfg.threshold_multiplier_step,
                )
            else:
                self._state.multiplier = max(
                    1.0,
                    self._state.multiplier - cfg.recovery_rate,
                )

        # Adaptive threshold
        h_mean = float(heatmap.mean())
        h_std = float(heatmap.std())
        base = h_mean + self._state.multiplier * h_std
        budget_factor = min(1.0, self.remaining_budget_ms() / cfg.target_latency_ms)
        threshold = base + (1.0 - budget_factor) * h_std

        # Dynamic K
        k = max(1, int(self.remaining_budget_ms() / cfg.avg_filter_latency_ms))

        return (threshold, k, "normal")

    def record_cc_count(self, count: int) -> None:
        self._state.recent_cc_counts.append(count)
        if len(self._state.recent_cc_counts) > self.config.window_size:
            self._state.recent_cc_counts.pop(0)

    def _estimate_cc_count(self, heatmap: np.ndarray) -> int:
        """Fast estimate: count pixels above a low threshold as an upper bound."""
        low_thresh = heatmap.mean() + 0.5 * heatmap.std()
        return int((heatmap > low_thresh).sum() / 16)
