from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np


@dataclass
class VLMRequest:
    original_image: np.ndarray | None = None
    heatmap_image: np.ndarray | None = None
    crop_image: np.ndarray | None = None
    cluster_representative_paths: list[str] = field(default_factory=list)
    cluster_metadata: dict[str, object] = field(default_factory=dict)
    prompt_override: str | None = None


@dataclass
class VLMResult:
    anomaly_type: str
    is_false_alarm: bool
    reason: str
    confidence: float
    suggestion: str
    raw_response: str | None = None


class VLMAnalyzer(Protocol):
    async def analyze(self, request: VLMRequest) -> VLMResult:
        ...

    async def batch_analyze(
        self, requests: list[VLMRequest]
    ) -> list[VLMResult]:
        ...

    @property
    def model_name(self) -> str:
        ...
