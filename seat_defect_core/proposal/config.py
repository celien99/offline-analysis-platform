from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BudgetScope(Enum):
    """Controls what the budget controller is allowed to throttle."""
    PROPOSAL = "proposal"
    PROPOSAL_AND_FILTER = "proposal_and_filter"
    FULL_PIPELINE = "full_pipeline"


@dataclass
class BudgetConfig:
    """Configuration for adaptive budget control."""
    enabled: bool = True
    scope: BudgetScope = BudgetScope.PROPOSAL_AND_FILTER
    target_latency_ms: float = 15.0
    hard_limit_ms: float = 20.0
    max_cc_before_emergency: int = 50
    avg_filter_latency_ms: float = 3.0
    window_size: int = 100
    threshold_multiplier_step: float = 0.5
    threshold_multiplier_max: float = 3.0
    recovery_rate: float = 0.01


@dataclass
class ProposalConfig:
    """Configuration for region proposal generation."""
    # Heatmap thresholding
    heatmap_threshold_mode: str = "adaptive"  # "adaptive" or "fixed"
    heatmap_threshold_fixed: float = 0.5
    heatmap_adaptive_std_multiplier: float = 1.5

    # Connected component filtering
    min_component_area: int = 16  # pixels
    min_solidity: float = 0.3
    max_proposals: int = 20

    # Morphological cleanup
    open_kernel_size: int = 3
    close_kernel_size: int = 5

    # Bounding box expansion
    context_padding_ratio: float = 0.10
    min_crop_size: int = 20

    # Aggregation
    aggregation_method: str = "weighted_confidence"
    area_exponent: float = 0.5
    confidence_threshold: float = 0.5
    budget: BudgetConfig | None = None
