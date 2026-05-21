from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from app.common.types import AnomalyId, EmbeddingArray, ModelVersionId


class EmbeddingExtractor(Protocol):
    async def extract(self, image: np.ndarray) -> np.ndarray:
        ...

    @property
    def model_name(self) -> str:
        ...

    @property
    def dimension(self) -> int:
        ...


@dataclass
class EmbeddingVector:
    anomaly_id: AnomalyId
    vector: list[float]
    model_name: str = "resnet18"
    model_version: str | None = None
    dimension: int = 512
