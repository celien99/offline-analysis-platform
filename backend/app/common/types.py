from __future__ import annotations

from datetime import datetime
from typing import TypeAlias
from uuid import UUID  # noqa: F401  # kept for external consumers

import numpy as np

# Domain identifiers
AnomalyId: TypeAlias = str
ClusterId: TypeAlias = str
EmbeddingId: TypeAlias = str
CameraId: TypeAlias = str
RegionId: TypeAlias = str
SeatModelId: TypeAlias = str
ModelVersionId: TypeAlias = str
ReviewId: TypeAlias = str
TraceId: TypeAlias = str

# Data types
EmbeddingArray: TypeAlias = np.ndarray
ImageData: TypeAlias = bytes
JsonDict: TypeAlias = dict[str, object]
Timestamp: TypeAlias = datetime
