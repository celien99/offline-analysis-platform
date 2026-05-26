from __future__ import annotations

from dataclasses import dataclass


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
