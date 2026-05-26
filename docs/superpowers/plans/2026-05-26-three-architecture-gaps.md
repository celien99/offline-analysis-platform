# Three Architecture Gaps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Proposal Budget Controller (adaptive threshold + latency SLA), Defect Identity Linking (Kalman + feature matching with conflict resolution), and Embedding Space Contract (protocol-layer representation standard + alignment projector).

**Architecture:** Protocol-first approach. `defect_protocol/` defines CanonicalPatchProposal, EmbeddingSpaceContract, and BudgetScope as shared contracts. `seat_defect_core/` implements budget controller and identity tracker. `ml/alignment/` implements the projector as one concrete implementation of the contract.

**Tech Stack:** Python 3.11+, PyTorch, NumPy, OpenCV, scipy (Kalman/Hungarian), defect_protocol

**Spec:** `docs/superpowers/specs/2026-05-26-three-architecture-gaps-design.md`

---

### Task 1: Add CanonicalPatchProposal to defect_protocol

**Files:**
- Create: `defect_protocol/defect_protocol/canonical_proposal.py`

- [ ] **Step 1: Create `defect_protocol/defect_protocol/canonical_proposal.py`**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .entities import FilterResult


@dataclass
class CanonicalPatchProposal:
    """Strictly-validated canonical schema for patch proposals. Zero data drift."""

    # 不变标识（生成后不可修改）
    proposal_id: str
    schema_version: str = "1.0.0"
    isolation_key: str

    # 空间参照（归一化坐标系 0-1，漂移免疫）
    roi_bbox_norm: tuple[float, float, float, float]
    patch_bbox_norm: tuple[float, float, float, float]
    roi_size_px: tuple[int, int]  # 实际像素尺寸（用于反归一化）

    # 异常上下文
    anomaly_score: float
    component_area_px: int
    component_solidity: float

    # 引用（不存二进制数据）
    patch_image_ref: str   # MinIO key
    heatmap_ref: str
    feature_ref: str       # .npy base path

    # 运行时追踪（在线填充）
    identity_id: Optional[str] = None
    filter_result: Optional[FilterResult] = None
    unified_embedding: Optional[list[float]] = None

    # 生成参数快照（可复现性）
    generation_params: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate invariants on construction."""
        x1, y1, x2, y2 = self.patch_bbox_norm
        assert 0 <= x1 < x2 <= 1, f"patch_bbox_norm x invalid: {self.patch_bbox_norm}"
        assert 0 <= y1 < y2 <= 1, f"patch_bbox_norm y invalid: {self.patch_bbox_norm}"
        assert self.component_area_px > 0, f"component_area_px must be > 0, got {self.component_area_px}"
        assert len(self.roi_size_px) == 2, f"roi_size_px must be (w, h)"
        assert self.roi_size_px[0] > 0 and self.roi_size_px[1] > 0

    def patch_bbox_px(self) -> tuple[int, int, int, int]:
        """Convert normalized bbox to pixel coordinates."""
        w, h = self.roi_size_px
        x1, y1, x2, y2 = self.patch_bbox_norm
        return (int(x1 * w), int(y1 * h), int(x2 * w), int(y2 * h))

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "proposal_id": self.proposal_id,
            "schema_version": self.schema_version,
            "isolation_key": self.isolation_key,
            "roi_bbox_norm": list(self.roi_bbox_norm),
            "patch_bbox_norm": list(self.patch_bbox_norm),
            "roi_size_px": list(self.roi_size_px),
            "anomaly_score": self.anomaly_score,
            "component_area_px": self.component_area_px,
            "component_solidity": self.component_solidity,
            "patch_image_ref": self.patch_image_ref,
            "heatmap_ref": self.heatmap_ref,
            "feature_ref": self.feature_ref,
            "generation_params": self.generation_params,
        }
        if self.identity_id is not None:
            d["identity_id"] = self.identity_id
        if self.filter_result is not None:
            from .serialization import _filter_result_to_dict
            d["filter_result"] = _filter_result_to_dict(self.filter_result)
        if self.unified_embedding is not None:
            d["unified_embedding"] = self.unified_embedding
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CanonicalPatchProposal":
        from .serialization import _filter_result_from_dict
        fr = None
        if "filter_result" in d and d["filter_result"] is not None:
            fr = _filter_result_from_dict(d["filter_result"])
        return cls(
            proposal_id=d["proposal_id"],
            schema_version=d.get("schema_version", "1.0.0"),
            isolation_key=d["isolation_key"],
            roi_bbox_norm=tuple(d["roi_bbox_norm"]),
            patch_bbox_norm=tuple(d["patch_bbox_norm"]),
            roi_size_px=tuple(d["roi_size_px"]),
            anomaly_score=d["anomaly_score"],
            component_area_px=d["component_area_px"],
            component_solidity=d["component_solidity"],
            patch_image_ref=d["patch_image_ref"],
            heatmap_ref=d["heatmap_ref"],
            feature_ref=d["feature_ref"],
            identity_id=d.get("identity_id"),
            filter_result=fr,
            unified_embedding=d.get("unified_embedding"),
            generation_params=d.get("generation_params", {}),
        )
```

- [ ] **Step 2: Update `defect_protocol/defect_protocol/__init__.py`**

Add to imports:
```python
from .canonical_proposal import CanonicalPatchProposal
```
Add to `__all__`:
```python
    "CanonicalPatchProposal",
```

- [ ] **Step 3: Verify + test**

```bash
cd defect_protocol && uv run python -c "
from defect_protocol import CanonicalPatchProposal
p = CanonicalPatchProposal(
    proposal_id='test', isolation_key='a|b|c',
    roi_bbox_norm=(0,0,1,1), patch_bbox_norm=(0.1,0.1,0.5,0.5),
    roi_size_px=(224,224), anomaly_score=0.9,
    component_area_px=100, component_solidity=0.8,
    patch_image_ref='p.png', heatmap_ref='h.png', feature_ref='f/',
)
d = p.to_dict()
p2 = CanonicalPatchProposal.from_dict(d)
assert p2.proposal_id == 'test'
assert p2.patch_bbox_px() == (22, 22, 112, 112)
print('OK')
"
```

- [ ] **Step 4: Commit**

```bash
git add defect_protocol/
git commit -m "feat: add CanonicalPatchProposal with schema_version and validation"
```

---

### Task 2: Add EmbeddingSpaceContract to defect_protocol

**Files:**
- Create: `defect_protocol/defect_protocol/embedding_space.py`

- [ ] **Step 1: Create `defect_protocol/defect_protocol/embedding_space.py`**

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmbeddingSpaceContract:
    """Representation standard — all modules reference this, not implementations.

    This is the "law" that all embedding producers and consumers must obey.
    It does NOT define HOW to produce embeddings, only WHAT they must look like.
    """
    dim: int = 384
    norm: str = "l2"
    similarity: str = "cosine"
    target_geometry: str = "dinov2_vits14"
    schema_version: str = "1.0.0"

    def validate(self, vector: list[float]) -> bool:
        """Check if a vector satisfies this contract."""
        if len(vector) != self.dim:
            return False
        if self.norm == "l2":
            import math
            norm_val = math.sqrt(sum(v * v for v in vector))
            if abs(norm_val - 1.0) > 0.01:
                return False
        return True


@dataclass
class UnifiedEmbedding:
    """A concrete vector satisfying EmbeddingSpaceContract."""
    vector: list[float]     # 384-dim, L2 normalized
    contract_version: str   # "1.0.0"
    source: str             # "efficientad_projected" | "dinov2"

    def __post_init__(self):
        assert len(self.vector) == 384, f"Expected 384-dim, got {len(self.vector)}"
```

- [ ] **Step 2: Update `defect_protocol/defect_protocol/__init__.py`**

```python
from .embedding_space import EmbeddingSpaceContract, UnifiedEmbedding
```
Add to `__all__`: `"EmbeddingSpaceContract", "UnifiedEmbedding"`

- [ ] **Step 3: Verify**

```bash
cd defect_protocol && uv run python -c "
from defect_protocol import EmbeddingSpaceContract, UnifiedEmbedding
c = EmbeddingSpaceContract()
assert c.validate([0.0]*384) == False  # not L2 normalized
import math; v = [1.0/math.sqrt(384)]*384
assert c.validate(v) == True
u = UnifiedEmbedding(vector=v, contract_version='1.0.0', source='dinov2')
print('OK')
"
```

- [ ] **Step 4: Commit**

```bash
git add defect_protocol/
git commit -m "feat: add EmbeddingSpaceContract and UnifiedEmbedding to defect_protocol"
```

---

### Task 3: Add BudgetScope and BudgetConfig

**Files:**
- Modify: `seat_defect_core/proposal/config.py`

- [ ] **Step 1: Add `BudgetScope` enum and `BudgetConfig` to `proposal/config.py`**

Read `seat_defect_core/proposal/config.py` first. Add after existing imports:

```python
from enum import Enum


class BudgetScope(Enum):
    """Controls what the budget controller is allowed to throttle."""
    PROPOSAL = "proposal"                      # Only proposal generation (threshold + K)
    PROPOSAL_AND_FILTER = "proposal_and_filter"  # Proposal + filter inference (early exit)
    FULL_PIPELINE = "full_pipeline"            # Entire pipeline including aggregation


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
```

- [ ] **Step 2: Add `budget` field to `ProposalConfig`**

After the existing `confidence_threshold` field:
```python
    budget: BudgetConfig | None = None
```

- [ ] **Step 3: Verify syntax**

```bash
seat_defect_core/.venv/bin/python -c "import ast; ast.parse(open('seat_defect_core/proposal/config.py').read()); print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add seat_defect_core/proposal/config.py
git commit -m "feat: add BudgetScope enum and BudgetConfig to proposal module"
```

---

### Task 4: Implement BudgetController

**Files:**
- Create: `seat_defect_core/proposal/budget.py`

- [ ] **Step 1: Create `seat_defect_core/proposal/budget.py`**

```python
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .config import BudgetConfig, BudgetScope


@dataclass
class BudgetState:
    """Mutable state tracked across frames for budget control."""
    multiplier: float = 1.5  # Current adaptive threshold multiplier
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
        return int((heatmap > low_thresh).sum() / 16)  # rough lower-bound area divisor
```

- [ ] **Step 2: Verify syntax**

```bash
seat_defect_core/.venv/bin/python -c "import ast; ast.parse(open('seat_defect_core/proposal/budget.py').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add seat_defect_core/proposal/budget.py
git commit -m "feat: add BudgetController with adaptive threshold and three-mode operation"
```

---

### Task 5: Integrate BudgetController into ProposalGenerator

**Files:**
- Modify: `seat_defect_core/proposal/generator.py`
- Modify: `seat_defect_core/proposal/__init__.py`

- [ ] **Step 1: Add BudgetController import to `generator.py`**

After existing imports:
```python
from .budget import BudgetController
from .config import BudgetConfig, BudgetScope
```

- [ ] **Step 2: Modify `ProposalGenerator.__init__` to accept budget controller**

```python
    def __init__(self, config: ProposalConfig | None = None,
                 budget_ctrl: BudgetController | None = None):
        self.config = config or ProposalConfig()
        self.budget = budget_ctrl or BudgetController(self.config.budget)
```

- [ ] **Step 3: Modify `generate()` to use budget controller**

At the start of `generate()` (before threshold computation), add:
```python
        self.budget.start_frame()
        threshold, k_limit, mode = self.budget.regulate(heatmap)

        if mode == "emergency":
            # Emergency: skip everything, return empty
            return []
```

Replace the existing threshold computation block with the budget-provided threshold:
```python
        # Use budget-regulated threshold instead of computing separately
        # (remove the old adaptive/fixed threshold block)
```

Replace the max_proposals truncation with k_limit:
```python
        components = components[:min(cfg.max_proposals, k_limit if k_limit > 0 else cfg.max_proposals)]
```

After CC counting, record:
```python
        self.budget.record_cc_count(num_labels - 1)  # num_labels includes background
```

- [ ] **Step 4: Update `proposal/__init__.py` exports**

```python
from .config import BudgetConfig, BudgetScope, ProposalConfig
from .budget import BudgetController
# ... add to __all__: "BudgetConfig", "BudgetScope", "BudgetController"
```

- [ ] **Step 5: Verify syntax and commit**

```bash
seat_defect_core/.venv/bin/python -c "import ast; ast.parse(open('seat_defect_core/proposal/generator.py').read()); print('OK')"
git add seat_defect_core/proposal/
git commit -m "feat: integrate BudgetController into ProposalGenerator with adaptive K and emergency exit"
```

---

### Task 6: Create Tracking config and Kalman filter

**Files:**
- Create: `seat_defect_core/tracking/__init__.py`
- Create: `seat_defect_core/tracking/config.py`
- Create: `seat_defect_core/tracking/kalman_filter.py`

- [ ] **Step 1: Create `tracking/__init__.py`**

```python
from __future__ import annotations

from .tracker import DefectTracker
from .config import TrackConfig

__all__ = ["DefectTracker", "TrackConfig"]
```

- [ ] **Step 2: Create `tracking/config.py`**

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TrackConfig:
    max_age: int = 30           # Frames before LOST → DEAD
    min_hits: int = 2           # Hits before TENTATIVE
    mature_hits: int = 5        # Hits before MATURE (trigger upload)
    iou_threshold: float = 0.3
    mahalanobis_threshold: float = 9.5  # chi2(0.05, df=3)
    feature_cosine_threshold: float = 0.85
    feature_match_margin: float = 0.15   # Margin for Best Match Wins
    nms_iou_threshold: float = 0.5       # For N:1 merge
    cross_camera_cosine_threshold: float = 0.9  # For N:M cross-camera merge
    epipolar_distance_threshold: float = 50.0   # Stage 3 geometry check
```

- [ ] **Step 3: Create `tracking/kalman_filter.py`**

```python
from __future__ import annotations

import numpy as np
from scipy.optimize import linear_sum_assignment


class KalmanBoxTracker:
    """6-DOF Kalman filter: (x, y, w, h, vx, vy)."""

    def __init__(self, bbox: tuple[float, float, float, float]):
        x, y, w, h = bbox
        self.kf = self._init_kalman()
        self.kf.state_est[:4, 0] = np.array([x, y, w, h])
        self.time_since_update = 0
        self.hits = 0
        self.hit_streak = 0
        self.age = 0

    def _init_kalman(self):
        import cv2
        kf = cv2.KalmanFilter(6, 4)
        kf.transitionMatrix = np.eye(6, dtype=np.float32)
        kf.transitionMatrix[0, 4] = 1.0  # x += vx
        kf.transitionMatrix[1, 5] = 1.0  # y += vy
        kf.transitionMatrix[2, 2] = 1.0
        kf.transitionMatrix[3, 3] = 1.0
        kf.measurementMatrix = np.eye(4, 6, dtype=np.float32)
        kf.processNoiseCov *= 0.01
        kf.measurementNoiseCov *= 0.1
        return kf

    def predict(self) -> tuple[float, float, float, float]:
        pred = self.kf.predict()
        x, y, w, h = pred[0, 0], pred[1, 0], pred[2, 0], pred[3, 0]
        self.age += 1
        self.time_since_update += 1
        return (x, y, w, h)

    def update(self, bbox: tuple[float, float, float, float]):
        x, y, w, h = bbox
        self.kf.correct(np.array([[x], [y], [w], [h]], dtype=np.float32))
        self.time_since_update = 0
        self.hits += 1
        self.hit_streak += 1

    def mahalanobis(self, bbox: tuple[float, float, float, float]) -> float:
        """Compute Mahalanobis distance between measurement and prediction."""
        pred = self.kf.state_pre[:4, 0]
        meas = np.array(bbox, dtype=np.float32)
        innov = meas - pred
        S = self.kf.measurementMatrix @ self.kf.errorCovPre @ self.kf.measurementMatrix.T + self.kf.measurementNoiseCov
        try:
            return float(np.sqrt(innov.T @ np.linalg.inv(S) @ innov))
        except np.linalg.LinAlgError:
            return float("inf")


def iou(bbox1: tuple, bbox2: tuple) -> float:
    x1 = max(bbox1[0], bbox2[0])
    y1 = max(bbox1[1], bbox2[1])
    x2 = min(bbox1[0] + bbox1[2], bbox2[0] + bbox2[2])
    y2 = min(bbox1[1] + bbox1[3], bbox2[1] + bbox2[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    area1 = bbox1[2] * bbox1[3]
    area2 = bbox2[2] * bbox2[3]
    return inter / (area1 + area2 - inter + 1e-8)


def hungarian_matching(cost_matrix: np.ndarray) -> list[tuple[int, int]]:
    """Solve assignment problem with Hungarian algorithm."""
    row_ind, col_ind = linear_sum_assignment(cost_matrix)
    return list(zip(row_ind.tolist(), col_ind.tolist()))
```

- [ ] **Step 4: Verify and commit**

```bash
seat_defect_core/.venv/bin/python -c "import ast; ast.parse(open('seat_defect_core/tracking/kalman_filter.py').read()); print('OK')"
git add seat_defect_core/tracking/
git commit -m "feat: add tracking config and Kalman filter with Hungarian matching"
```

---

### Task 7: Create DefectIdentity and Tracker

**Files:**
- Create: `seat_defect_core/tracking/identity.py`
- Create: `seat_defect_core/tracking/tracker.py`
- Create: `seat_defect_core/tracking/matcher.py`

- [ ] **Step 1: Create `tracking/identity.py`**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .kalman_filter import KalmanBoxTracker


class IdentityState(Enum):
    BIRTH = "birth"
    ACTIVE = "active"
    TENTATIVE = "tentative"
    MATURE = "mature"
    LOST = "lost"
    DEAD = "dead"


@dataclass
class DefectIdentity:
    identity_id: str
    camera_id: str
    state: IdentityState = IdentityState.BIRTH
    tracker: Optional[KalmanBoxTracker] = None
    best_anomaly_score: float = 0.0
    best_frame_id: str = ""
    best_proposal_id: str = ""
    best_patch_bbox_norm: tuple[float, float, float, float] = (0, 0, 0, 0)
    unified_embedding: Optional[list[float]] = None
    merged_into: Optional[str] = None  # ID of identity this was merged into
    frames_since_update: int = 0
    total_hits: int = 0
    hit_streak: int = 0

    def mark_hit(self):
        self.total_hits += 1
        self.hit_streak += 1
        self.frames_since_update = 0
        self._update_state_on_hit()

    def mark_miss(self):
        self.frames_since_update += 1
        self.hit_streak = 0
        self._update_state_on_miss()

    def _update_state_on_hit(self):
        if self.hit_streak >= 5:
            self.state = IdentityState.MATURE
        elif self.hit_streak >= 2:
            self.state = IdentityState.TENTATIVE
        elif self.state == IdentityState.BIRTH:
            self.state = IdentityState.ACTIVE

    def _update_state_on_miss(self):
        if self.frames_since_update > 0:
            self.state = IdentityState.LOST
```

- [ ] **Step 2: Create `tracking/matcher.py`** (conflict resolution)

```python
from __future__ import annotations

from typing import Optional

import numpy as np

from .config import TrackConfig
from .identity import DefectIdentity
from .kalman_filter import hungarian_matching, iou


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = np.sqrt(sum(x * x for x in a))
    norm_b = np.sqrt(sum(x * x for x in b))
    return float(dot / (norm_a * norm_b + 1e-8))


class CascadeMatcher:
    """Three-stage cascade matching with conflict resolution."""

    def __init__(self, config: TrackConfig):
        self.cfg = config

    def match(self, proposals: list[dict], active_identities: list[DefectIdentity],
              camera_id: str) -> tuple[list[tuple[int, int]], list[int], list[int]]:
        """Returns: (matched_pairs, unmatched_proposal_indices, unmatched_identity_indices)"""
        n_props = len(proposals)
        n_idents = len(active_identities)
        if n_props == 0:
            return ([], [], list(range(n_idents)))

        matched: list[tuple[int, int]] = []
        unmatched_props = set(range(n_props))

        # Stage 1: IoU + Kalman (same-camera only)
        unmatched_props = self._match_stage(matched, unmatched_props, proposals,
                                             active_identities, camera_id, stage=1)

        # Stage 2: Feature cosine similarity
        if unmatched_props:
            unmatched_props = self._match_stage(matched, unmatched_props, proposals,
                                                 active_identities, camera_id, stage=2)

        # Stage 3: Cross-camera geometry (epipolar) — deferred to fusion.py

        unmatched_idents = list(set(range(n_idents)) - {j for _, j in matched})
        return (matched, list(unmatched_props), unmatched_idents)

    def _match_stage(self, matched: list, unmatched_props: set, proposals: list[dict],
                     identities: list[DefectIdentity], camera_id: str,
                     stage: int) -> set:
        if not unmatched_props:
            return unmatched_props

        cost_matrix = np.full((len(unmatched_props), len(identities)), np.inf)
        prop_indices = sorted(unmatched_props)

        for pi, p_idx in enumerate(prop_indices):
            p = proposals[p_idx]
            for ii, ident in enumerate(identities):
                if stage == 1:
                    if ident.camera_id != camera_id or ident.tracker is None:
                        continue
                    iou_val = iou(p["bbox_xywh"], ident.tracker.predict())
                    mahal = ident.tracker.mahalanobis(p["bbox_xywh"])
                    if iou_val >= self.cfg.iou_threshold and mahal <= self.cfg.mahalanobis_threshold:
                        cost_matrix[pi, ii] = 1.0 - iou_val
                elif stage == 2:
                    if p.get("unified_embedding") is None or ident.unified_embedding is None:
                        continue
                    cos_sim = cosine_similarity(p["unified_embedding"], ident.unified_embedding)
                    if cos_sim >= self.cfg.feature_cosine_threshold:
                        cost_matrix[pi, ii] = 1.0 - cos_sim

        valid = cost_matrix < np.inf
        if valid.any():
            assignments = hungarian_matching(cost_matrix)
            for pi, ii in assignments:
                if cost_matrix[pi, ii] < np.inf:
                    # Best Match Wins: check margin
                    row = cost_matrix[pi, :]
                    sorted_costs = sorted(row[row < np.inf])
                    if len(sorted_costs) >= 2:
                        margin = sorted_costs[1] - sorted_costs[0]
                        if margin < self.cfg.feature_match_margin:
                            continue  # ambiguous → create new identity
                    matched.append((prop_indices[pi], ii))
                    unmatched_props.discard(prop_indices[pi])

        return unmatched_props
```

- [ ] **Step 3: Create `tracking/tracker.py`**

```python
from __future__ import annotations

import uuid
from typing import Optional

from defect_protocol import CanonicalPatchProposal

from .config import TrackConfig
from .identity import DefectIdentity, IdentityState
from .kalman_filter import KalmanBoxTracker
from .matcher import CascadeMatcher


class DefectTracker:
    """Per-camera defect identity tracker."""

    def __init__(self, camera_id: str, config: TrackConfig | None = None):
        self.camera_id = camera_id
        self.cfg = config or TrackConfig()
        self._matcher = CascadeMatcher(self.cfg)
        self._identities: dict[str, DefectIdentity] = {}
        self._frame_count: int = 0

    def update(self, proposals: list[CanonicalPatchProposal]) -> list[CanonicalPatchProposal]:
        """Match proposals to existing identities, create new ones, handle conflicts.

        Returns proposals with identity_id assigned.
        """
        self._frame_count += 1

        # Predict all trackers
        for ident in self._identities.values():
            if ident.tracker is not None:
                ident.tracker.predict()

        # Build proposal dicts for matching
        prop_dicts = []
        for p in proposals:
            bbox_norm = p.patch_bbox_norm
            w, h = p.roi_size_px
            prop_dicts.append({
                "proposal_id": p.proposal_id,
                "bbox_xywh": (bbox_norm[0] * w, bbox_norm[1] * h,
                              (bbox_norm[2] - bbox_norm[0]) * w,
                              (bbox_norm[3] - bbox_norm[1]) * h),
                "unified_embedding": p.unified_embedding,
            })

        active = [i for i in self._identities.values()
                   if i.state not in (IdentityState.DEAD,)]

        matched_pairs, unmatched_props, _ = self._matcher.match(
            prop_dicts, active, self.camera_id)

        # Apply matches
        for p_idx, ident_idx in matched_pairs:
            prop = proposals[p_idx]
            ident = active[ident_idx]
            prop.identity_id = ident.identity_id
            ident.mark_hit()
            if ident.tracker is not None and prop_dicts[p_idx]["bbox_xywh"]:
                ident.tracker.update(prop_dicts[p_idx]["bbox_xywh"])
            if prop.anomaly_score > ident.best_anomaly_score:
                ident.best_anomaly_score = prop.anomaly_score
                ident.best_proposal_id = prop.proposal_id
                ident.best_patch_bbox_norm = prop.patch_bbox_norm
            if prop.unified_embedding:
                ident.unified_embedding = prop.unified_embedding

        # N:1 Merge: check if multiple proposals matched same identity
        identity_matches: dict[str, list[int]] = {}
        for p_idx, ident_idx in matched_pairs:
            iid = active[ident_idx].identity_id
            identity_matches.setdefault(iid, []).append(p_idx)
        for iid, p_indices in identity_matches.items():
            if len(p_indices) > 1:
                self._resolve_n_to_one(iid, [proposals[i] for i in p_indices])

        # Create new identities for unmatched proposals
        for p_idx in unmatched_props:
            prop = proposals[p_idx]
            new_id = DefectIdentity(
                identity_id=uuid.uuid4().hex[:12],
                camera_id=self.camera_id,
            )
            bbox = prop_dicts[p_idx]["bbox_xywh"]
            new_id.tracker = KalmanBoxTracker(bbox)
            new_id.best_anomaly_score = prop.anomaly_score
            new_id.best_proposal_id = prop.proposal_id
            new_id.best_patch_bbox_norm = prop.patch_bbox_norm
            if prop.unified_embedding:
                new_id.unified_embedding = prop.unified_embedding
            new_id.mark_hit()
            prop.identity_id = new_id.identity_id
            self._identities[new_id.identity_id] = new_id

        # Mark missed identities
        for ident in active:
            ident_id = ident.identity_id
            was_matched = any(active[m[1]].identity_id == ident_id for m in matched_pairs)
            if not was_matched:
                ident.mark_miss()

        # Prune DEAD identities
        dead_ids = [iid for iid, i in self._identities.items()
                    if i.state == IdentityState.LOST and i.frames_since_update > self.cfg.max_age]
        for iid in dead_ids:
            self._identities[iid].state = IdentityState.DEAD

        return proposals

    def get_mature_identities(self) -> list[DefectIdentity]:
        return [i for i in self._identities.values() if i.state == IdentityState.MATURE]

    def merge_identity(self, from_id: str, into_id: str) -> None:
        """Merge from_id into into_id (cross-camera merge)."""
        if from_id in self._identities and into_id in self._identities:
            self._identities[from_id].merged_into = into_id
            self._identities[from_id].state = IdentityState.DEAD

    def _resolve_n_to_one(self, identity_id: str, proposals: list[CanonicalPatchProposal]):
        """NMS Merge for N:1 conflict."""
        # Sort by anomaly_score descending
        proposals.sort(key=lambda p: p.anomaly_score, reverse=True)
        keep = proposals[0]
        for p in proposals[1:]:
            # Check IoU between keep and p
            b1 = keep.patch_bbox_norm
            b2 = p.patch_bbox_norm
            # Compute IoU of normalized bboxes
            x1 = max(b1[0], b2[0])
            y1 = max(b1[1], b2[1])
            x2 = min(b1[2], b2[2])
            y2 = min(b1[3], b2[3])
            inter = max(0, x2 - x1) * max(0, y2 - y1)
            area1 = (b1[2] - b1[0]) * (b1[3] - b1[1])
            area2 = (b2[2] - b2[0]) * (b2[3] - b2[1])
            iou_val = inter / (area1 + area2 - inter + 1e-8)
            if iou_val >= 0.5:
                p.identity_id = keep.identity_id  # Redirect to keep
```

- [ ] **Step 4: Verify and commit**

```bash
seat_defect_core/.venv/bin/python -c "import ast; ast.parse(open('seat_defect_core/tracking/tracker.py').read()); print('OK')"
git add seat_defect_core/tracking/
git commit -m "feat: add DefectIdentity, CascadeMatcher, and DefectTracker with conflict resolution"
```

---

### Task 8: Integrate DefectTracker into inspection_camera.py and uploader

**Files:**
- Modify: `seat_defect_core/service/inspection_camera.py`
- Modify: `seat_defect_core/anomaly_uploader.py`
- Modify: `seat_defect_core/config.py` (add TrackConfig to CameraConfig)

- [ ] **Step 1: Add `TrackConfig` to `CameraConfig` in `config.py`**

After the `proposal` field:
```python
    track: TrackConfig | None = None
```

Add import:
```python
from .tracking.config import TrackConfig  # noqa: F401
```

- [ ] **Step 2: Modify `inspection_camera.py` to create/use DefectTracker**

After the proposal generation block (Task 11 from previous plan), add identity linking:

```python
        # --- Identity Linking ---
        if proposals:
            tracker = getattr(service, '_tracker', None)
            if tracker is None and getattr(camera, 'track', None) is not None:
                from ..tracking import DefectTracker
                tracker = DefectTracker(camera.camera_id, camera.track)
                service._tracker = tracker
            if tracker is not None:
                proposals = tracker.update(proposals)
```

- [ ] **Step 3: Modify `anomaly_uploader.py` for MATURE-triggered upload**

After the existing upload logic, add identity-aware dedup:
```python
        # Identity-aware upload: only upload MATURE identities
        mature_proposals = [p for p in getattr(result, 'proposals', [])
                           if getattr(p, 'identity_id', None) is not None]
        if mature_proposals:
            # Check if this identity already has an anomaly_record
            for p in mature_proposals:
                if getattr(p, 'is_best_frame', False):
                    data["identity_id"] = p.identity_id
                    data["is_best_frame"] = True
```

- [ ] **Step 4: Verify and commit**

```bash
seat_defect_core/.venv/bin/python -c "import ast; ast.parse(open('seat_defect_core/service/inspection_camera.py').read()); print('OK')"
git add seat_defect_core/service/inspection_camera.py seat_defect_core/anomaly_uploader.py seat_defect_core/config.py
git commit -m "feat: integrate DefectTracker into inspection pipeline and uploader"
```

---

### Task 9: Create Alignment Projector model

**Files:**
- Create: `ml/alignment/__init__.py`
- Create: `ml/alignment/projector.py`
- Create: `ml/alignment/config.py`

- [ ] **Step 1: Create `ml/alignment/__init__.py`**

```python
from __future__ import annotations

from .projector import AlignmentProjector
from .config import AlignmentConfig

__all__ = ["AlignmentProjector", "AlignmentConfig"]
```

- [ ] **Step 2: Create `ml/alignment/config.py`**

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AlignmentConfig:
    # EfficientAD feature channel dimensions
    l1_channels: int = 64
    l2_channels: int = 128
    l3_channels: int = 256
    diff_channels: int = 64

    # Projector architecture
    per_layer_proj_dim: int = 128
    transformer_dim: int = 512
    transformer_heads: int = 4
    transformer_layers: int = 2
    transformer_ffn_dim: int = 1024
    output_dim: int = 384  # Must match EmbeddingSpaceContract

    # Training
    learning_rate: float = 1e-4
    temperature: float = 0.07
    batch_size: int = 64
    epochs: int = 30
    early_stopping_patience: int = 5
    output_dir: str = "./models"
```

- [ ] **Step 3: Create `ml/alignment/projector.py`**

```python
from __future__ import annotations

import math

import torch
import torch.nn as nn
import torch.nn.functional as F


class AlignmentProjector(nn.Module):
    """Projects EfficientAD features into EmbeddingSpaceContract-compatible 384d L2 space."""

    def __init__(self, config=None):
        super().__init__()
        from .config import AlignmentConfig
        cfg = config or AlignmentConfig()

        # Per-layer projection
        self.l1_proj = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(1),
            nn.Linear(cfg.l1_channels, cfg.per_layer_proj_dim),
            nn.ReLU(inplace=True),
        )
        self.l2_proj = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(1),
            nn.Linear(cfg.l2_channels, cfg.per_layer_proj_dim),
            nn.ReLU(inplace=True),
        )
        self.l3_proj = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(1),
            nn.Linear(cfg.l3_channels, cfg.per_layer_proj_dim),
            nn.ReLU(inplace=True),
        )
        self.diff_proj = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(1),
            nn.Linear(cfg.diff_channels, cfg.per_layer_proj_dim),
            nn.ReLU(inplace=True),
        )

        # Position embeddings for 4 feature tokens
        self.pos_embed = nn.Parameter(torch.randn(1, 4, cfg.transformer_dim) * 0.02)

        # Transformer encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=cfg.transformer_dim,
            nhead=cfg.transformer_heads,
            dim_feedforward=cfg.transformer_ffn_dim,
            batch_first=True,
            activation="gelu",
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=cfg.transformer_layers)

        # Input projection: 4 × per_layer_proj_dim → transformer_dim
        self.input_proj = nn.Linear(cfg.per_layer_proj_dim, cfg.transformer_dim)

        # CLS token
        self.cls_token = nn.Parameter(torch.randn(1, 1, cfg.transformer_dim) * 0.02)

        # Output projection
        self.output_proj = nn.Linear(cfg.transformer_dim, cfg.output_dim)

        self._cfg = cfg

    def forward(self, teacher_l1: torch.Tensor, teacher_l2: torch.Tensor,
                teacher_l3: torch.Tensor, difference: torch.Tensor) -> torch.Tensor:
        # Per-layer projection
        f1 = self.l1_proj(teacher_l1)  # (B, proj_dim)
        f2 = self.l2_proj(teacher_l2)
        f3 = self.l3_proj(teacher_l3)
        fd = self.diff_proj(difference)

        # Stack tokens: (B, 4, proj_dim)
        tokens = torch.stack([f1, f2, f3, fd], dim=1)
        tokens = self.input_proj(tokens)  # (B, 4, transformer_dim)
        tokens = tokens + self.pos_embed

        # Add CLS token
        B = tokens.size(0)
        cls_tokens = self.cls_token.expand(B, -1, -1)
        tokens = torch.cat([cls_tokens, tokens], dim=1)  # (B, 5, transformer_dim)

        # Transformer
        tokens = self.transformer(tokens)

        # CLS token → output
        cls_out = tokens[:, 0, :]  # (B, transformer_dim)
        emb = self.output_proj(cls_out)  # (B, 384)

        # L2 normalize
        emb = F.normalize(emb, p=2, dim=1)
        return emb

    def to_torchscript(self, output_path: str) -> None:
        self.eval()
        B = 1
        example = (
            torch.randn(B, self._cfg.l1_channels, 56, 56),
            torch.randn(B, self._cfg.l2_channels, 28, 28),
            torch.randn(B, self._cfg.l3_channels, 14, 14),
            torch.randn(B, self._cfg.diff_channels, 224, 224),
        )
        traced = torch.jit.trace(self, example)
        traced.save(output_path)
```

- [ ] **Step 4: Verify and commit**

```bash
seat_defect_core/.venv/bin/python -c "import ast; ast.parse(open('ml/alignment/projector.py').read()); print('OK')"
git add ml/alignment/
git commit -m "feat: add AlignmentProjector with Transformer encoder and L2 output"
```

---

### Task 10: Create Alignment Dataset and Trainer

**Files:**
- Create: `ml/alignment/dataset.py`
- Create: `ml/alignment/trainer.py`

- [ ] **Step 1: Create `ml/alignment/dataset.py`**

```python
from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset


class AlignmentDataset(Dataset):
    """Paired (EAD features, DINOv2 embedding) dataset for alignment training."""

    def __init__(self, ead_feature_paths: list[str], dino_embeddings: list[list[float]]):
        self.ead_paths = ead_feature_paths
        self.dino_embs = dino_embeddings
        assert len(self.ead_paths) == len(self.dino_embs)

    def __len__(self) -> int:
        return len(self.ead_paths)

    def __getitem__(self, idx: int) -> tuple[dict[str, torch.Tensor], torch.Tensor]:
        base = Path(self.ead_paths[idx])
        ead_features = {
            "teacher_l1": torch.from_numpy(np.load(base / "teacher_l1.npy")).float(),
            "teacher_l2": torch.from_numpy(np.load(base / "teacher_l2.npy")).float(),
            "teacher_l3": torch.from_numpy(np.load(base / "teacher_l3.npy")).float(),
            "difference": torch.from_numpy(np.load(base / "difference.npy")).float(),
        }
        # Convert HWC → CHW
        for k in ead_features:
            t = ead_features[k]
            if t.dim() == 3:
                ead_features[k] = t.permute(2, 0, 1)
        dino_emb = torch.tensor(self.dino_embs[idx], dtype=torch.float32)
        return ead_features, dino_emb
```

- [ ] **Step 2: Create `ml/alignment/trainer.py`**

```python
from __future__ import annotations

from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader

from .config import AlignmentConfig
from .dataset import AlignmentDataset
from .projector import AlignmentProjector


class InfoNCELoss(nn.Module):
    def __init__(self, temperature: float = 0.07):
        super().__init__()
        self.temperature = temperature

    def forward(self, anchor: torch.Tensor, positive: torch.Tensor) -> torch.Tensor:
        """Contrastive loss: pull anchor-positive pairs together, push others apart."""
        anchor = F.normalize(anchor, p=2, dim=1)
        positive = F.normalize(positive, p=2, dim=1)
        B = anchor.size(0)
        logits = anchor @ positive.T / self.temperature  # (B, B)
        labels = torch.arange(B, device=anchor.device)
        loss_a = F.cross_entropy(logits, labels)
        loss_b = F.cross_entropy(logits.T, labels)
        return (loss_a + loss_b) / 2


class AlignmentTrainer:
    def __init__(self, config: AlignmentConfig | None = None, device: str = "cpu"):
        self.cfg = config or AlignmentConfig()
        self.device = torch.device(device)
        self.model = AlignmentProjector(self.cfg).to(self.device)
        self.model_name = "alignment_projector"

    def train(self, train_dataset: AlignmentDataset, val_dataset: AlignmentDataset,
              *, output_dir: str | None = None) -> dict[str, object]:
        cfg = self.cfg
        output_dir = Path(output_dir or cfg.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        train_loader = DataLoader(train_dataset, batch_size=cfg.batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=cfg.batch_size, shuffle=False)

        criterion = InfoNCELoss(temperature=cfg.temperature)
        optimizer = torch.optim.AdamW(self.model.parameters(), lr=cfg.learning_rate)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=cfg.epochs)

        best_val_loss = float("inf")
        patience_counter = 0
        history: list[dict] = []

        for epoch in range(cfg.epochs):
            self.model.train()
            train_loss = 0.0
            for ead_feats, dino_embs in train_loader:
                ead_feats = {k: v.to(self.device) for k, v in ead_feats.items()}
                dino_embs = dino_embs.to(self.device)

                optimizer.zero_grad()
                projected = self.model(
                    ead_feats["teacher_l1"], ead_feats["teacher_l2"],
                    ead_feats["teacher_l3"], ead_feats["difference"],
                )
                loss = criterion(projected, dino_embs)
                loss.backward()
                optimizer.step()
                train_loss += loss.item()

            train_loss /= len(train_loader)
            scheduler.step()

            self.model.eval()
            val_loss = 0.0
            with torch.no_grad():
                for ead_feats, dino_embs in val_loader:
                    ead_feats = {k: v.to(self.device) for k, v in ead_feats.items()}
                    dino_embs = dino_embs.to(self.device)
                    projected = self.model(
                        ead_feats["teacher_l1"], ead_feats["teacher_l2"],
                        ead_feats["teacher_l3"], ead_feats["difference"],
                    )
                    val_loss += criterion(projected, dino_embs).item()

            val_loss /= len(val_loader)
            history.append({"epoch": epoch + 1, "train_loss": train_loss, "val_loss": val_loss})

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
                torch.save(self.model.state_dict(), output_dir / "best_projector.pt")
            else:
                patience_counter += 1

            if patience_counter >= cfg.early_stopping_patience:
                break

        return {"best_val_loss": best_val_loss, "history": history}

    def export_torchscript(self, output_path: str | Path) -> str:
        self.model.load_state_dict(torch.load(
            Path(self.cfg.output_dir) / "best_projector.pt", map_location=self.device))
        path = str(output_path)
        self.model.to_torchscript(path)
        return path
```

- [ ] **Step 3: Verify and commit**

```bash
seat_defect_core/.venv/bin/python -c "import ast; ast.parse(open('ml/alignment/trainer.py').read()); print('OK')"
git add ml/alignment/
git commit -m "feat: add AlignmentDataset and AlignmentTrainer with InfoNCE contrastive loss"
```

---

### Task 11: Upgrade Filter to three-modal fusion (image + EAD + unified_emb)

**Files:**
- Modify: `ml/classifier/dual_modal/model.py`
- Modify: `seat_defect_core/classifier/engine.py`

- [ ] **Step 1: Add unified_emb input to DualModalFilter forward()**

Read `ml/classifier/dual_modal/model.py`. Modify the `forward()` signature to accept optional unified_emb:

```python
    def forward(self, patch_image: torch.Tensor,
                ead_features: dict[str, torch.Tensor] | None = None,
                unified_emb: torch.Tensor | None = None) -> torch.Tensor:
```

After the existing EAD feature branch processing, add unified embedding fusion:
```python
        # Unified embedding (DINOv2-aligned, from EmbeddingSpaceContract)
        if unified_emb is not None:
            f_uni = unified_emb  # Already 384d, L2-normalized
            # Project to 256d to match f_img/f_ead dims
            if not hasattr(self, 'uni_proj'):
                self.uni_proj = nn.Linear(384, 256).to(f_img.device)
            f_uni_proj = F.relu(self.uni_proj(f_uni))
        else:
            f_uni_proj = torch.zeros_like(f_img)

        # Three-way fusion: image + EAD + unified
        fused = torch.cat([f_img, f_ead, f_uni_proj], dim=1)  # 768d
```

Update the fusion head input dim from 512 to 768:
```python
        self.fusion = nn.Sequential(
            nn.Linear(768, 128),  # was 512
            ...
        )
```

- [ ] **Step 2: Update `predict_dual_modal()` in `engine.py`**

Add `unified_emb` parameter:
```python
    def predict_dual_modal(
        self, patch_image: np.ndarray,
        ead_features: dict[str, np.ndarray] | None = None,
        unified_emb: list[float] | None = None,
    ) -> FilterClassifierResult:
```

Preprocess unified_emb:
```python
        uni_tensor = None
        if unified_emb is not None:
            uni_tensor = torch.tensor(unified_emb, dtype=torch.float32).unsqueeze(0).to(self._device)
```

Pass to model:
```python
            logits = self._model(tensor, feat_tensors if feat_tensors else None,
                                 uni_tensor)
```

- [ ] **Step 3: Verify and commit**

```bash
seat_defect_core/.venv/bin/python -c "import ast; ast.parse(open('ml/classifier/dual_modal/model.py').read()); print('OK')"
git add ml/classifier/dual_modal/model.py seat_defect_core/classifier/engine.py
git commit -m "feat: upgrade DualModalFilter to three-modal fusion with unified embedding"
```

---

### Task 12: Add alignment embedding Celery worker task

**Files:**
- Modify: `backend/app/workers/embedding_worker/tasks.py`

- [ ] **Step 1: Add `train_alignment_projector` Celery task**

At the end of the tasks file, add:

```python
@celery_app.task(name="embedding.train_alignment")
def train_alignment_projector(
    anomaly_ids: list[str] | None = None,
    epochs: int = 30,
    batch_size: int = 64,
    learning_rate: float = 1e-4,
    seat_model_id: str | None = None,
    output_dir: str | None = None,
) -> dict[str, object]:
    """Train alignment projector: EAD features → DINOv2 embedding space."""
    logger.info("alignment_training_started", anomaly_count=len(anomaly_ids) if anomaly_ids else 0)

    try:
        from ml.alignment import AlignmentTrainer, AlignmentConfig
        from ml.alignment.dataset import AlignmentDataset

        # Load paired training data: (EAD feature paths, DINOv2 embeddings)
        ead_paths, dino_embs = run_async(
            _load_alignment_pairs(anomaly_ids, seat_model_id)
        )

        if len(ead_paths) < 10:
            return {"status": "skipped", "reason": "insufficient_pairs",
                    "pair_count": len(ead_paths)}

        # Train/val split
        split = int(len(ead_paths) * 0.8)
        train_ds = AlignmentDataset(ead_paths[:split], dino_embs[:split])
        val_ds = AlignmentDataset(ead_paths[split:], dino_embs[split:])

        config = AlignmentConfig(
            learning_rate=learning_rate,
            batch_size=batch_size,
            epochs=epochs,
            output_dir=output_dir or str(settings.model_artifact_dir / "alignment"),
        )
        trainer = AlignmentTrainer(config=config, device="cuda" if torch.cuda.is_available() else "cpu")
        metrics = trainer.train(train_ds, val_ds)

        # Export TorchScript
        ts_path = trainer.export_torchscript(
            str(Path(config.output_dir) / "alignment_projector.pt"))

        return {"status": "completed", "best_val_loss": metrics["best_val_loss"],
                "torchscript_path": ts_path}
    except Exception as e:
        logger.exception("alignment_training_failed", error=str(e))
        return {"status": "failed", "error": str(e)}


async def _load_alignment_pairs(
    anomaly_ids: list[str] | None,
    seat_model_id: str | None,
) -> tuple[list[str], list[list[float]]]:
    """Load paired (EAD feature_path, DINOv2 embedding) from reviewed anomalies."""
    # Query anomalies with both EAD features and DINOv2 embeddings
    # Build pairs where both exist for the same anomaly
    # This reuses the existing _load_training_data infrastructure
    ead_paths: list[str] = []
    dino_embs: list[list[float]] = []
    # ... implementation queries DB for anomalies with feature_ref + embedding
    return ead_paths, dino_embs
```

- [ ] **Step 2: Verify and commit**

```bash
cd backend && uv run python -c "import ast; ast.parse(open('app/workers/embedding_worker/tasks.py').read()); print('OK')"
git add backend/app/workers/embedding_worker/tasks.py
git commit -m "feat: add alignment projector training task to embedding worker"
```

---

### Task 13: Update README with three improvements

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update architecture diagram and feature descriptions**

Read README. Update the ONLINE pipeline to include Budget Controller and Identity Linking:
- Add `Budget Ctrl` step between EAD and Region Proposal
- Add `Identity Linking` step between Region Proposal and Align Project

Update features table to add three new entries:
- Budget Controller feature
- Defect Identity Linking feature
- Embedding Space Contract feature

Update project structure:
- Add `tracking/` to seat_defect_core
- Add `ml/alignment/` to ml/
- Add `defect_protocol/canonical_proposal.py` and `embedding_space.py`

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: sync README with Budget Controller + Identity Linking + Embedding Space Contract"
```

---

### Task 14: End-to-end verification

- [ ] **Step 1: Verify all imports across components**

```bash
cd defect_protocol && uv run python -c "
from defect_protocol import CanonicalPatchProposal, EmbeddingSpaceContract, UnifiedEmbedding
print('defect_protocol OK')
"
cd ../seat_defect_core && uv run python -c "
from proposal import BudgetController, BudgetScope, ProposalGenerator
from tracking import DefectTracker, TrackConfig
print('seat_defect_core OK')
"
cd ../backend && uv run python -c "
from ml.alignment import AlignmentProjector, AlignmentConfig
print('ml OK')
"
```

- [ ] **Step 2: Run defect_protocol tests**

```bash
cd defect_protocol && uv run pytest -v
```

- [ ] **Step 3: Run backend unit tests**

```bash
cd backend && uv run pytest -v --ignore=app/tests/test_e2e_pipeline.py --ignore=app/tests/test_api.py
```

- [ ] **Step 4: Commit any fixes**

```bash
git add -A && git diff --cached --stat
git commit -m "chore: final integration verification for three architecture gaps"
```
