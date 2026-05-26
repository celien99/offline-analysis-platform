# EfficientAD → Filter Architecture Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the online detection pipeline from scalar anomaly_score to patch-level anomaly representation, add region proposal refinement (heatmap → CC → crop → Filter), and replace the existing FilterClassifier with a dual-modal (image + EfficientAD features) architecture.

**Architecture:** Shared protocol package (`defect_protocol/`) defines the unified `PatchProposal` data contract. `seat_defect_core` implements online feature harvesting and region proposal. `ml/classifier/dual_modal/` implements the new trainer. Backend schemas and training worker are upgraded accordingly.

**Tech Stack:** Python 3.11+, PyTorch, NumPy, OpenCV, FastAPI, SQLAlchemy async, MinIO, Celery

**Spec:** `docs/superpowers/specs/2026-05-26-efficientad-filter-architecture-design.md`

---

### Task 1: Create `defect_protocol/` shared data protocol package

**Files:**
- Create: `defect_protocol/__init__.py`
- Create: `defect_protocol/types.py`
- Create: `defect_protocol/entities.py`
- Create: `defect_protocol/serialization.py`
- Create: `defect_protocol/pyproject.toml`

- [ ] **Step 1: Create `defect_protocol/pyproject.toml`**

```toml
[project]
name = "defect_protocol"
version = "0.1.0"
description = "Shared data protocol for online inference and offline training"
requires-python = ">=3.11"
dependencies = []

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

- [ ] **Step 2: Create `defect_protocol/types.py`**

```python
from __future__ import annotations

from typing import NewType

ProposalId = NewType("ProposalId", str)
FeatureRef = NewType("FeatureRef", str)
ImageRef = NewType("ImageRef", str)
IsolationKeyStr = NewType("IsolationKeyStr", str)
```

- [ ] **Step 3: Create `defect_protocol/entities.py`**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .types import FeatureRef, ImageRef, IsolationKeyStr, ProposalId


@dataclass
class BoundingBox:
    x1: float
    y1: float
    x2: float
    y2: float

    def area(self) -> float:
        return (self.x2 - self.x1) * (self.y2 - self.y1)

    def to_tuple(self) -> tuple[float, float, float, float]:
        return (self.x1, self.y1, self.x2, self.y2)

    @classmethod
    def from_tuple(cls, t: tuple[float, float, float, float]) -> "BoundingBox":
        return cls(x1=t[0], y1=t[1], x2=t[2], y2=t[3])


@dataclass
class EfficientADFeatures:
    """Multi-scale teacher features + student-teacher difference."""
    teacher_l1_ref: FeatureRef
    teacher_l2_ref: FeatureRef
    teacher_l3_ref: FeatureRef
    difference_ref: FeatureRef
    # Shapes for reconstruction without loading .npy
    teacher_l1_shape: tuple[int, int, int] = (56, 56, 64)
    teacher_l2_shape: tuple[int, int, int] = (28, 28, 128)
    teacher_l3_shape: tuple[int, int, int] = (14, 14, 256)
    difference_shape: tuple[int, int, int] = (224, 224, 64)


@dataclass
class ROIContext:
    """Parent ROI metadata."""
    roi_bbox: BoundingBox
    roi_image_ref: ImageRef
    roi_size: tuple[int, int]  # (width, height)


@dataclass
class AnomalyContext:
    """EfficientAD anomaly context for this patch."""
    anomaly_score: float
    anomaly_threshold: float
    heatmap_ref: ImageRef
    feature_ref: FeatureRef  # MinIO key prefix for .npy files


@dataclass
class ImageRef:
    """Reference to an image stored in MinIO."""
    key: str
    width: int = 0
    height: int = 0


@dataclass
class ProposalMetadata:
    """Proposal generation metadata."""
    component_area: int
    component_solidity: float
    rank: int
    total_proposals: int
    generation_params: dict = field(default_factory=dict)


@dataclass
class FilterResult:
    """Per-patch filter classification result."""
    is_real_defect: bool
    confidence: float
    real_defect_score: float
    false_alarm_score: float
    class_id: int
    diagnostics: dict[str, float] = field(default_factory=dict)


@dataclass
class PatchProposal:
    """Unified patch-level anomaly proposal — the core data contract."""
    proposal_id: ProposalId
    isolation_key: IsolationKeyStr  # "seat_model_id|camera_id|region_id"
    source_roi: ROIContext
    patch_image: ImageRef
    patch_bbox: BoundingBox
    anomaly_context: AnomalyContext
    efficientad_features: EfficientADFeatures
    proposal_metadata: ProposalMetadata
    filter_result: Optional[FilterResult] = None
```

- [ ] **Step 4: Create `defect_protocol/serialization.py`**

```python
from __future__ import annotations

import json
from typing import Any

from .entities import (
    AnomalyContext,
    BoundingBox,
    EfficientADFeatures,
    FilterResult,
    ImageRef,
    PatchProposal,
    ProposalMetadata,
    ROIContext,
)


def _bbox_to_dict(b: BoundingBox) -> dict[str, float]:
    return {"x1": b.x1, "y1": b.y1, "x2": b.x2, "y2": b.y2}


def _bbox_from_dict(d: dict[str, float]) -> BoundingBox:
    return BoundingBox(x1=d["x1"], y1=d["y1"], x2=d["x2"], y2=d["y2"])


def _image_ref_to_dict(r: ImageRef) -> dict[str, Any]:
    return {"key": r.key, "width": r.width, "height": r.height}


def _image_ref_from_dict(d: dict[str, Any]) -> ImageRef:
    return ImageRef(key=d["key"], width=d.get("width", 0), height=d.get("height", 0))


def _roi_context_to_dict(r: ROIContext) -> dict[str, Any]:
    return {
        "roi_bbox": _bbox_to_dict(r.roi_bbox),
        "roi_image_ref": _image_ref_to_dict(r.roi_image_ref),
        "roi_size": list(r.roi_size),
    }


def _roi_context_from_dict(d: dict[str, Any]) -> ROIContext:
    return ROIContext(
        roi_bbox=_bbox_from_dict(d["roi_bbox"]),
        roi_image_ref=_image_ref_from_dict(d["roi_image_ref"]),
        roi_size=(d["roi_size"][0], d["roi_size"][1]),
    )


def _anomaly_context_to_dict(a: AnomalyContext) -> dict[str, Any]:
    return {
        "anomaly_score": a.anomaly_score,
        "anomaly_threshold": a.anomaly_threshold,
        "heatmap_ref": _image_ref_to_dict(a.heatmap_ref),
        "feature_ref": a.feature_ref,
    }


def _anomaly_context_from_dict(d: dict[str, Any]) -> AnomalyContext:
    return AnomalyContext(
        anomaly_score=d["anomaly_score"],
        anomaly_threshold=d["anomaly_threshold"],
        heatmap_ref=_image_ref_from_dict(d["heatmap_ref"]),
        feature_ref=d["feature_ref"],
    )


def _features_to_dict(f: EfficientADFeatures) -> dict[str, Any]:
    return {
        "teacher_l1_ref": f.teacher_l1_ref,
        "teacher_l2_ref": f.teacher_l2_ref,
        "teacher_l3_ref": f.teacher_l3_ref,
        "difference_ref": f.difference_ref,
        "teacher_l1_shape": list(f.teacher_l1_shape),
        "teacher_l2_shape": list(f.teacher_l2_shape),
        "teacher_l3_shape": list(f.teacher_l3_shape),
        "difference_shape": list(f.difference_shape),
    }


def _features_from_dict(d: dict[str, Any]) -> EfficientADFeatures:
    return EfficientADFeatures(
        teacher_l1_ref=d["teacher_l1_ref"],
        teacher_l2_ref=d["teacher_l2_ref"],
        teacher_l3_ref=d["teacher_l3_ref"],
        difference_ref=d["difference_ref"],
        teacher_l1_shape=tuple(d["teacher_l1_shape"]),
        teacher_l2_shape=tuple(d["teacher_l2_shape"]),
        teacher_l3_shape=tuple(d["teacher_l3_shape"]),
        difference_shape=tuple(d["difference_shape"]),
    )


def _proposal_meta_to_dict(m: ProposalMetadata) -> dict[str, Any]:
    return {
        "component_area": m.component_area,
        "component_solidity": m.component_solidity,
        "rank": m.rank,
        "total_proposals": m.total_proposals,
        "generation_params": m.generation_params,
    }


def _proposal_meta_from_dict(d: dict[str, Any]) -> ProposalMetadata:
    return ProposalMetadata(
        component_area=d["component_area"],
        component_solidity=d["component_solidity"],
        rank=d["rank"],
        total_proposals=d["total_proposals"],
        generation_params=d.get("generation_params", {}),
    )


def _filter_result_to_dict(f: FilterResult) -> dict[str, Any]:
    return {
        "is_real_defect": f.is_real_defect,
        "confidence": f.confidence,
        "real_defect_score": f.real_defect_score,
        "false_alarm_score": f.false_alarm_score,
        "class_id": f.class_id,
        "diagnostics": f.diagnostics,
    }


def _filter_result_from_dict(d: dict[str, Any]) -> FilterResult:
    return FilterResult(
        is_real_defect=d["is_real_defect"],
        confidence=d["confidence"],
        real_defect_score=d["real_defect_score"],
        false_alarm_score=d["false_alarm_score"],
        class_id=d["class_id"],
        diagnostics=d.get("diagnostics", {}),
    )


def proposal_to_dict(p: PatchProposal) -> dict[str, Any]:
    result: dict[str, Any] = {
        "proposal_id": p.proposal_id,
        "isolation_key": p.isolation_key,
        "source_roi": _roi_context_to_dict(p.source_roi),
        "patch_image": _image_ref_to_dict(p.patch_image),
        "patch_bbox": _bbox_to_dict(p.patch_bbox),
        "anomaly_context": _anomaly_context_to_dict(p.anomaly_context),
        "efficientad_features": _features_to_dict(p.efficientad_features),
        "proposal_metadata": _proposal_meta_to_dict(p.proposal_metadata),
    }
    if p.filter_result is not None:
        result["filter_result"] = _filter_result_to_dict(p.filter_result)
    return result


def proposal_from_dict(d: dict[str, Any]) -> PatchProposal:
    filter_result = None
    if "filter_result" in d and d["filter_result"] is not None:
        filter_result = _filter_result_from_dict(d["filter_result"])
    return PatchProposal(
        proposal_id=d["proposal_id"],
        isolation_key=d["isolation_key"],
        source_roi=_roi_context_from_dict(d["source_roi"]),
        patch_image=_image_ref_from_dict(d["patch_image"]),
        patch_bbox=_bbox_from_dict(d["patch_bbox"]),
        anomaly_context=_anomaly_context_from_dict(d["anomaly_context"]),
        efficientad_features=_features_from_dict(d["efficientad_features"]),
        proposal_metadata=_proposal_meta_from_dict(d["proposal_metadata"]),
        filter_result=filter_result,
    )


def proposals_to_json(proposals: list[PatchProposal]) -> str:
    return json.dumps([proposal_to_dict(p) for p in proposals], ensure_ascii=False)


def proposals_from_json(json_str: str) -> list[PatchProposal]:
    return [proposal_from_dict(d) for d in json.loads(json_str)]
```

- [ ] **Step 5: Create `defect_protocol/__init__.py`**

```python
from __future__ import annotations

from .entities import (
    AnomalyContext,
    BoundingBox,
    EfficientADFeatures,
    FilterResult,
    ImageRef,
    PatchProposal,
    ProposalMetadata,
    ROIContext,
)
from .serialization import (
    proposal_from_dict,
    proposal_to_dict,
    proposals_from_json,
    proposals_to_json,
)
from .types import FeatureRef, ImageRef, IsolationKeyStr, ProposalId

__all__ = [
    "AnomalyContext",
    "BoundingBox",
    "EfficientADFeatures",
    "FeatureRef",
    "FilterResult",
    "ImageRef",
    "IsolationKeyStr",
    "PatchProposal",
    "ProposalId",
    "ProposalMetadata",
    "ROIContext",
    "proposal_from_dict",
    "proposal_to_dict",
    "proposals_from_json",
    "proposals_to_json",
]
```

- [ ] **Step 6: Install defect_protocol in dev mode**

```bash
cd defect_protocol && uv pip install -e .
```

- [ ] **Step 7: Verify import works**

```bash
python -c "from defect_protocol import PatchProposal, proposal_to_dict, proposal_from_dict; print('OK')"
```

Expected: `OK`

- [ ] **Step 8: Commit**

```bash
git add defect_protocol/
git commit -m "feat: add defect_protocol shared data protocol package

Defines PatchProposal, EfficientADFeatures, and serialization as the
unified data contract between online inference and offline training."
```

---

### Task 2: Test defect_protocol serialization round-trip

**Files:**
- Create: `defect_protocol/tests/test_serialization.py`

- [ ] **Step 1: Create `defect_protocol/tests/test_serialization.py`**

```python
from __future__ import annotations

from defect_protocol import (
    AnomalyContext,
    BoundingBox,
    EfficientADFeatures,
    FilterResult,
    ImageRef,
    PatchProposal,
    ProposalMetadata,
    ROIContext,
    proposal_from_dict,
    proposal_to_dict,
    proposals_from_json,
    proposals_to_json,
)


def make_proposal() -> PatchProposal:
    return PatchProposal(
        proposal_id="test-pid-001",
        isolation_key="model_a|cam_front|region_seat",
        source_roi=ROIContext(
            roi_bbox=BoundingBox(10, 20, 200, 300),
            roi_image_ref=ImageRef(key="roi/test.jpg", width=224, height=224),
            roi_size=(224, 224),
        ),
        patch_image=ImageRef(key="patches/test_patch.png", width=64, height=64),
        patch_bbox=BoundingBox(50, 60, 114, 124),
        anomaly_context=AnomalyContext(
            anomaly_score=0.92,
            anomaly_threshold=0.5,
            heatmap_ref=ImageRef(key="heatmaps/test.png"),
            feature_ref="features/model_a/cam_front/2026-05-26/test-pid-001",
        ),
        efficientad_features=EfficientADFeatures(
            teacher_l1_ref="features/.../teacher_l1.npy",
            teacher_l2_ref="features/.../teacher_l2.npy",
            teacher_l3_ref="features/.../teacher_l3.npy",
            difference_ref="features/.../difference.npy",
        ),
        proposal_metadata=ProposalMetadata(
            component_area=1024,
            component_solidity=0.85,
            rank=1,
            total_proposals=3,
        ),
        filter_result=FilterResult(
            is_real_defect=True,
            confidence=0.87,
            real_defect_score=0.87,
            false_alarm_score=0.13,
            class_id=1,
        ),
    )


def test_proposal_round_trip():
    p = make_proposal()
    d = proposal_to_dict(p)
    p2 = proposal_from_dict(d)
    assert p2.proposal_id == p.proposal_id
    assert p2.isolation_key == p.isolation_key
    assert p2.patch_bbox.x1 == p.patch_bbox.x1
    assert p2.anomaly_context.anomaly_score == p.anomaly_context.anomaly_score
    assert p2.efficientad_features.teacher_l1_ref == p.efficientad_features.teacher_l1_ref
    assert p2.filter_result is not None
    assert p2.filter_result.confidence == 0.87


def test_proposal_without_filter_result():
    p = make_proposal()
    p.filter_result = None
    d = proposal_to_dict(p)
    assert "filter_result" not in d
    p2 = proposal_from_dict(d)
    assert p2.filter_result is None


def test_proposals_json_round_trip():
    proposals = [make_proposal(), make_proposal()]
    proposals[1].proposal_id = "test-pid-002"
    json_str = proposals_to_json(proposals)
    loaded = proposals_from_json(json_str)
    assert len(loaded) == 2
    assert loaded[1].proposal_id == "test-pid-002"


def test_bounding_box_area():
    b = BoundingBox(0, 0, 10, 20)
    assert b.area() == 200.0


def test_bounding_box_tuple():
    b = BoundingBox(1.0, 2.0, 3.0, 4.0)
    assert b.to_tuple() == (1.0, 2.0, 3.0, 4.0)
    b2 = BoundingBox.from_tuple((5.0, 6.0, 7.0, 8.0))
    assert b2.x1 == 5.0
```

- [ ] **Step 2: Run tests**

```bash
cd defect_protocol && python -m pytest tests/ -v
```

Expected: 5 tests PASS

- [ ] **Step 3: Commit**

```bash
git add defect_protocol/tests/
git commit -m "test: add defect_protocol serialization round-trip tests"
```

---

### Task 3: Create DualModalFilter model

**Files:**
- Create: `ml/classifier/dual_modal/__init__.py`
- Create: `ml/classifier/dual_modal/model.py`

- [ ] **Step 1: Create `ml/classifier/dual_modal/__init__.py`**

```python
from __future__ import annotations

from .model import DualModalFilter
from .config import DualModalConfig

__all__ = ["DualModalFilter", "DualModalConfig"]
```

- [ ] **Step 2: Create `ml/classifier/dual_modal/model.py`**

```python
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import models


class EfficientADFeatureProjector(nn.Module):
    """Project multi-scale EfficientAD features to fixed-dim embeddings."""

    def __init__(self, l1_channels: int = 64, l2_channels: int = 128,
                 l3_channels: int = 256, diff_channels: int = 64,
                 proj_dim: int = 64):
        super().__init__()
        self.l1_proj = nn.Conv2d(l1_channels, proj_dim, 1)
        self.l2_proj = nn.Conv2d(l2_channels, proj_dim, 1)
        self.l3_proj = nn.Conv2d(l3_channels, proj_dim, 1)
        self.diff_proj = nn.Conv2d(diff_channels, proj_dim, 1)
        self.output_dim = proj_dim * 4  # 256

    def forward(self, teacher_l1: torch.Tensor, teacher_l2: torch.Tensor,
                teacher_l3: torch.Tensor, difference: torch.Tensor) -> torch.Tensor:
        f1 = F.adaptive_avg_pool2d(self.l1_proj(teacher_l1), 1).flatten(1)
        f2 = F.adaptive_avg_pool2d(self.l2_proj(teacher_l2), 1).flatten(1)
        f3 = F.adaptive_avg_pool2d(self.l3_proj(teacher_l3), 1).flatten(1)
        fd = F.adaptive_avg_pool2d(self.diff_proj(difference), 1).flatten(1)
        return torch.cat([f1, f2, f3, fd], dim=1)


class DualModalFilter(nn.Module):
    """Dual-modal filter: image patch + EfficientAD features → binary classifier."""

    def __init__(self, num_classes: int = 2, image_size: int = 448,
                 feature_dropout_rate: float = 0.0):
        super().__init__()
        # Image branch
        backbone = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.IMAGENET1K_V1)
        self.image_backbone = nn.Sequential(*list(backbone.children())[:-1])
        # MobileNetV3-Small last channel is 576
        self.image_proj = nn.Sequential(
            nn.Linear(576, 256),
            nn.ReLU(inplace=True),
        )

        # EfficientAD feature branch
        self.ead_projector = EfficientADFeatureProjector()
        self.ead_proj = nn.Sequential(
            nn.Linear(256, 256),
            nn.ReLU(inplace=True),
        )

        # Fusion head
        self.fusion = nn.Sequential(
            nn.Linear(512, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(128, 64),
            nn.ReLU(inplace=True),
            nn.Linear(64, num_classes),
        )

        self.feature_dropout_rate = feature_dropout_rate
        self.image_size = image_size

    def forward(self, patch_image: torch.Tensor,
                ead_features: dict[str, torch.Tensor] | None = None) -> torch.Tensor:
        # Image branch
        img_feat = self.image_backbone(patch_image)
        img_feat = img_feat.flatten(1)
        f_img = self.image_proj(img_feat)

        # EfficientAD feature branch (with optional dropout for fallback training)
        if ead_features is not None and self.training and self.feature_dropout_rate > 0:
            if torch.rand(1).item() < self.feature_dropout_rate:
                ead_features = None

        if ead_features is not None:
            ead_feat = self.ead_projector(
                ead_features["teacher_l1"],
                ead_features["teacher_l2"],
                ead_features["teacher_l3"],
                ead_features["difference"],
            )
            f_ead = self.ead_proj(ead_feat)
        else:
            f_ead = torch.zeros_like(f_img)

        # Fusion
        fused = torch.cat([f_img, f_ead], dim=1)
        return self.fusion(fused)

    def to_torchscript(self, output_path: str) -> None:
        """Export to TorchScript for online inference."""
        self.eval()
        example_img = torch.randn(1, 3, self.image_size, self.image_size)
        example_features = {
            "teacher_l1": torch.randn(1, 64, 56, 56),
            "teacher_l2": torch.randn(1, 128, 28, 28),
            "teacher_l3": torch.randn(1, 256, 14, 14),
            "difference": torch.randn(1, 64, 224, 224),
        }
        traced = torch.jit.trace(self, (example_img, example_features))
        traced.save(output_path)
```

- [ ] **Step 3: Commit**

```bash
git add ml/classifier/dual_modal/__init__.py ml/classifier/dual_modal/model.py
git commit -m "feat: add DualModalFilter model with image + EfficientAD feature branches"
```

---

### Task 4: Create DualModalConfig and DualModalDataset

**Files:**
- Create: `ml/classifier/dual_modal/config.py`
- Create: `ml/classifier/dual_modal/dataset.py`

- [ ] **Step 1: Create `ml/classifier/dual_modal/config.py`**

```python
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DualModalConfig:
    """Configuration for DualModalFilter training."""
    # Model
    num_classes: int = 2
    image_size: int = 448
    feature_dropout_rate: float = 0.2

    # Training
    learning_rate: float = 1e-4
    image_branch_lr: float = 1e-5  # Lower LR for pretrained backbone
    batch_size: int = 32
    epochs: int = 50
    early_stopping_patience: int = 10
    validation_split: float = 0.2

    # Loss
    focal_gamma: float = 2.0
    focal_alpha: float = 0.75  # Weight for real_defect class

    # Augmentation
    enable_augmentation: bool = True
    rotation_degrees: float = 15.0

    # Output
    output_dir: str = "./models"
    class_names: list[str] = field(default_factory=lambda: ["false_alarm", "real_defect"])
```

- [ ] **Step 2: Create `ml/classifier/dual_modal/dataset.py`**

```python
from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms


IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def _build_transform(image_size: int, augment: bool = False) -> transforms.Compose:
    ops = [transforms.Resize((image_size, image_size))]
    if augment:
        ops.extend([
            transforms.RandomHorizontalFlip(),
            transforms.ColorJitter(brightness=0.1, contrast=0.1, saturation=0.1, hue=0.02),
            transforms.RandomRotation(degrees=15),
        ])
    ops.extend([
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])
    return transforms.Compose(ops)


class DualModalDataset(Dataset):
    """Dataset loading patch images + EfficientAD features + labels."""

    def __init__(self, images: list[np.ndarray], labels: list[int],
                 features_dir: Optional[str] = None,
                 proposal_ids: Optional[list[str]] = None,
                 image_size: int = 448, augment: bool = False):
        self.images = images
        self.labels = labels
        self.features_dir = Path(features_dir) if features_dir else None
        self.proposal_ids = proposal_ids or []
        self.transform = _build_transform(image_size, augment)

    def __len__(self) -> int:
        return len(self.images)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, Optional[dict[str, torch.Tensor]], int]:
        img_array = self.images[idx]
        if img_array.ndim == 3 and img_array.shape[2] == 3:
            img = Image.fromarray(img_array.astype(np.uint8))
        else:
            img = Image.fromarray(img_array.astype(np.uint8), mode="RGB")
        img_tensor = self.transform(img)
        label = self.labels[idx]

        ead_features = None
        if self.features_dir is not None and self.proposal_ids:
            pid = self.proposal_ids[idx]
            feat_dir = self.features_dir / pid
            try:
                ead_features = {
                    "teacher_l1": torch.from_numpy(np.load(feat_dir / "teacher_l1.npy")),
                    "teacher_l2": torch.from_numpy(np.load(feat_dir / "teacher_l2.npy")),
                    "teacher_l3": torch.from_numpy(np.load(feat_dir / "teacher_l3.npy")),
                    "difference": torch.from_numpy(np.load(feat_dir / "difference.npy")),
                }
            except (FileNotFoundError, OSError):
                ead_features = None

        return img_tensor, ead_features, label
```

- [ ] **Step 3: Commit**

```bash
git add ml/classifier/dual_modal/config.py ml/classifier/dual_modal/dataset.py
git commit -m "feat: add DualModalConfig and DualModalDataset with feature loading"
```

---

### Task 5: Create DualModalTrainer

**Files:**
- Create: `ml/classifier/dual_modal/trainer.py`

- [ ] **Step 1: Create `ml/classifier/dual_modal/trainer.py`**

```python
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader

from .config import DualModalConfig
from .dataset import DualModalDataset
from .model import DualModalFilter


class FocalLoss(nn.Module):
    def __init__(self, gamma: float = 2.0, alpha: float = 0.75):
        super().__init__()
        self.gamma = gamma
        self.alpha = alpha

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        ce_loss = F.cross_entropy(logits, targets, reduction="none")
        pt = torch.exp(-ce_loss)
        alpha_t = torch.where(targets == 1, self.alpha, 1 - self.alpha)
        return (alpha_t * (1 - pt) ** self.gamma * ce_loss).mean()


class DualModalTrainer:
    def __init__(self, config: DualModalConfig | None = None, device: str = "cpu"):
        self.config = config or DualModalConfig()
        self.device = torch.device(device)
        self.model = DualModalFilter(
            num_classes=self.config.num_classes,
            image_size=self.config.image_size,
            feature_dropout_rate=self.config.feature_dropout_rate,
        ).to(self.device)
        self.model_name = "dual_modal_filter"

    def train(self, train_dataset: DualModalDataset, val_dataset: DualModalDataset,
              *, output_dir: str | None = None) -> dict[str, object]:
        config = self.config
        output_dir = Path(output_dir or config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        train_loader = DataLoader(train_dataset, batch_size=config.batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=config.batch_size, shuffle=False)

        criterion = FocalLoss(gamma=config.focal_gamma, alpha=config.focal_alpha)
        optimizer = torch.optim.Adam([
            {"params": self.model.image_backbone.parameters(), "lr": config.image_branch_lr},
            {"params": self.model.image_proj.parameters(), "lr": config.learning_rate},
            {"params": self.model.ead_projector.parameters(), "lr": config.learning_rate},
            {"params": self.model.ead_proj.parameters(), "lr": config.learning_rate},
            {"params": self.model.fusion.parameters(), "lr": config.learning_rate},
        ])
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode="min", factor=0.5, patience=5)

        best_val_loss = float("inf")
        best_epoch = 0
        patience_counter = 0
        history: list[dict] = []

        for epoch in range(config.epochs):
            self.model.train()
            train_loss = 0.0
            for imgs, features, labels in train_loader:
                imgs = imgs.to(self.device)
                labels = labels.to(self.device)
                if features is not None:
                    features = {k: v.to(self.device) for k, v in features.items()}

                optimizer.zero_grad()
                logits = self.model(imgs, features)
                loss = criterion(logits, labels)
                loss.backward()
                optimizer.step()
                train_loss += loss.item()

            train_loss /= len(train_loader)

            self.model.eval()
            val_loss = 0.0
            correct = 0
            total = 0
            with torch.no_grad():
                for imgs, features, labels in val_loader:
                    imgs = imgs.to(self.device)
                    labels = labels.to(self.device)
                    if features is not None:
                        features = {k: v.to(self.device) for k, v in features.items()}
                    logits = self.model(imgs, features)
                    val_loss += criterion(logits, labels).item()
                    preds = logits.argmax(dim=1)
                    correct += (preds == labels).sum().item()
                    total += labels.size(0)

            val_loss /= len(val_loader)
            val_acc = correct / total if total > 0 else 0.0
            scheduler.step(val_loss)

            history.append({"epoch": epoch + 1, "train_loss": train_loss,
                            "val_loss": val_loss, "val_acc": val_acc})

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                best_epoch = epoch + 1
                patience_counter = 0
                torch.save(self.model.state_dict(), output_dir / "best_model.pt")
            else:
                patience_counter += 1

            if patience_counter >= config.early_stopping_patience:
                break

        self.model.load_state_dict(torch.load(output_dir / "best_model.pt"))
        return {"best_val_loss": best_val_loss, "best_val_acc": val_acc,
                "best_epoch": best_epoch, "history": history,
                "early_stopped": patience_counter >= config.early_stopping_patience}

    def export_torchscript(self, output_path: str | Path) -> str:
        path = str(output_path)
        self.model.to_torchscript(path)
        return path

    def save_checkpoint(self, output_path: str | Path,
                        metrics: dict | None = None) -> str:
        path = str(output_path)
        checkpoint = {
            "model_state_dict": self.model.state_dict(),
            "config": self.config,
            "metrics": metrics or {},
        }
        torch.save(checkpoint, path)
        return path

    def load_checkpoint(self, checkpoint_path: str | Path) -> None:
        checkpoint = torch.load(str(checkpoint_path), map_location=self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
```

- [ ] **Step 2: Commit**

```bash
git add ml/classifier/dual_modal/trainer.py
git commit -m "feat: add DualModalTrainer with FocalLoss and dual learning rates"
```

---

### Task 6: Add feature harvesting to EfficientADService

**Files:**
- Modify: `seat_defect_core/efficientad/engine.py:29-117`

- [ ] **Step 1: Read current file to get exact content for editing**

```bash
head -130 seat_defect_core/efficientad/engine.py
```

- [ ] **Step 2: Add feature hook infrastructure to `engine.py`**

Add after imports (after line 26), before class definition (line 29):

```python
from typing import Any, Callable


class _FeatureHookManager:
    """Registers forward hooks on teacher/student layers to capture intermediate features."""

    def __init__(self):
        self._features: dict[str, torch.Tensor] = {}
        self._handles: list[torch.utils.hooks.RemovableHandle] = []

    def register(self, model: torch.nn.Module, teacher_blocks: list[str],
                 student_blocks: list[str]) -> None:
        for name, module in model.named_modules():
            for block_name in teacher_blocks:
                if name.endswith(block_name):
                    h = module.register_forward_hook(self._make_hook(f"teacher_{block_name}"))
                    self._handles.append(h)
            for block_name in student_blocks:
                if name.endswith(block_name):
                    h = module.register_forward_hook(self._make_hook(f"student_{block_name}"))
                    self._handles.append(h)

    def _make_hook(self, name: str) -> Callable:
        def hook(module, input, output):
            self._features[name] = output.detach() if isinstance(output, torch.Tensor) else output[0].detach()
        return hook

    def get_features(self) -> dict[str, torch.Tensor]:
        return dict(self._features)

    def compute_difference(self) -> torch.Tensor | None:
        """Compute |student - teacher| difference from captured features."""
        student_keys = [k for k in self._features if k.startswith("student_")]
        teacher_keys = [k for k in self._features if k.startswith("teacher_")]
        if not student_keys or not teacher_keys:
            return None
        # Sum absolute differences across matched layers
        diffs = []
        for sk, tk in zip(sorted(student_keys), sorted(teacher_keys)):
            s = self._features[sk]
            t = self._features[tk]
            if s.shape == t.shape:
                diffs.append(torch.abs(s - t).mean(dim=1, keepdim=True))
        if not diffs:
            return None
        return torch.cat(diffs, dim=1)

    def remove(self) -> None:
        for h in self._handles:
            h.remove()
        self._handles.clear()
        self._features.clear()
```

- [ ] **Step 3: Modify `EfficientADService.__init__` to initialize hook manager**

After `self._image_threshold = config.image_threshold` (line 38 in `_load_model` context, or after model load):

Add to `__init__` after model loading:
```python
        self._feature_hooks: _FeatureHookManager | None = None
        self._teacher_block_names = ["block1", "block2", "block3"]
```

- [ ] **Step 4: Add `predict_with_features` method to `EfficientADService`**

Add new method after `predict` (after line 117):

```python
    def predict_with_features(
        self, image: np.ndarray, target_mask: np.ndarray, ignore_mask: np.ndarray
    ) -> tuple[TextureAnomalyResult, dict[str, np.ndarray] | None]:
        """Predict anomaly score AND harvest intermediate features."""
        if not self._is_loaded:
            raise RuntimeError("Model not loaded")

        valid_ratio = _compute_valid_pixel_ratio(target_mask, ignore_mask, image.shape[:2])
        if valid_ratio < self.config.min_valid_pixel_ratio:
            result = TextureAnomalyResult(
                score=0.0, threshold=self._image_threshold, is_anomaly=False,
                heatmap=np.zeros(image.shape[:2], dtype=np.float32),
                anomaly_map=np.zeros(image.shape[:2], dtype=np.float32),
                valid_pixel_ratio=valid_ratio,
            )
            return result, None

        input_tensor = _prepare_input(image, self.config.input_size)

        # Register feature hooks
        hooks = _FeatureHookManager()
        hooks.register(self.model, self._teacher_block_names, [])

        with torch.no_grad():
            output = self.model(input_tensor)

        hooks.remove()

        # Parse anomaly output (same as predict())
        if isinstance(output, (list, tuple)):
            anomaly_map_tensor = output[0]
            raw_score = float(output[1].cpu().item()) if len(output) > 1 else 0.0
        elif isinstance(output, torch.Tensor):
            anomaly_map_tensor = output
            raw_score = float(anomaly_map_tensor.mean().cpu().item())
        else:
            anomaly_map_tensor = output
            raw_score = 0.0

        anomaly_map = _resize_anomaly_map(anomaly_map_tensor, image.shape[0], image.shape[1])
        if ignore_mask is not None and ignore_mask.any():
            ignore_bin = _to_binary_mask(ignore_mask, anomaly_map.shape)
            anomaly_map[ignore_bin > 0] = 0.0

        anomaly_score = float(anomaly_map.max())
        heatmap = (anomaly_map * 255).astype(np.uint8)

        result = TextureAnomalyResult(
            score=anomaly_score, threshold=self._image_threshold,
            is_anomaly=(anomaly_score > self._image_threshold),
            heatmap=heatmap, anomaly_map=anomaly_map,
            valid_pixel_ratio=valid_ratio,
        )

        # Extract feature arrays
        raw_features = hooks.get_features()
        features: dict[str, np.ndarray] = {}
        for name, tensor in raw_features.items():
            if tensor.dim() == 4:
                features[name] = tensor.cpu().numpy()
        # Compute difference if both teacher and student features present
        diff = hooks.compute_difference()
        if diff is not None:
            features["difference"] = diff.cpu().numpy()

        return result, features if features else None
```

- [ ] **Step 5: Commit**

```bash
git add seat_defect_core/efficientad/engine.py
git commit -m "feat: add feature harvesting via forward hooks in EfficientADService

Adds _FeatureHookManager and predict_with_features() to capture
teacher layer outputs and student-teacher difference during inference."
```

---

### Task 7: Update TextureAnomalyResult to carry features

**Files:**
- Modify: `seat_defect_core/core_types/results.py:12-33`

- [ ] **Step 1: Add `features` field to `TextureAnomalyResult`**

Replace the `TextureAnomalyResult` dataclass (lines 12-33):

```python
from typing import Optional

@dataclass
class TextureAnomalyResult:
    score: float
    threshold: float
    is_anomaly: bool
    heatmap: Any
    anomaly_map: Any
    valid_pixel_ratio: float = 1.0
    features: Optional[dict[str, Any]] = None  # EfficientAD intermediate features
```

- [ ] **Step 2: Commit**

```bash
git add seat_defect_core/core_types/results.py
git commit -m "feat: add features field to TextureAnomalyResult for EfficientAD feature harvesting"
```

---

### Task 8: Create Region Proposal module

**Files:**
- Create: `seat_defect_core/proposal/__init__.py`
- Create: `seat_defect_core/proposal/config.py`
- Create: `seat_defect_core/proposal/generator.py`
- Create: `seat_defect_core/proposal/aggregation.py`

- [ ] **Step 1: Create `seat_defect_core/proposal/__init__.py`**

```python
from __future__ import annotations

from .config import ProposalConfig
from .generator import ProposalGenerator
from .aggregation import aggregate_proposals

__all__ = ["ProposalConfig", "ProposalGenerator", "aggregate_proposals"]
```

- [ ] **Step 2: Create `seat_defect_core/proposal/config.py`**

```python
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
    aggregation_method: str = "weighted_confidence"  # "weighted_confidence" or "max_confidence"
    area_exponent: float = 0.5  # weight_i = area_i^exponent × score_i
    confidence_threshold: float = 0.5
```

- [ ] **Step 3: Create `seat_defect_core/proposal/generator.py`**

```python
from __future__ import annotations

from typing import Optional
import uuid

import cv2
import numpy as np

from defect_protocol import (
    AnomalyContext,
    BoundingBox,
    EfficientADFeatures,
    ImageRef,
    PatchProposal,
    ProposalMetadata,
    ROIContext,
)

from .config import ProposalConfig


class ProposalGenerator:
    """Generate PatchProposals from EfficientAD heatmap + features."""

    def __init__(self, config: ProposalConfig | None = None):
        self.config = config or ProposalConfig()

    def generate(self, heatmap: np.ndarray, roi_image: np.ndarray,
                 efficientad_features: dict[str, np.ndarray] | None,
                 anomaly_score: float, anomaly_threshold: float,
                 roi_bbox: tuple[int, int, int, int],
                 isolation_key: str,
                 roi_image_key: str = "") -> list[PatchProposal]:
        cfg = self.config

        # 1. Compute adaptive threshold
        if cfg.heatmap_threshold_mode == "adaptive":
            h_mean = float(heatmap.mean())
            h_std = float(heatmap.std())
            threshold = h_mean + cfg.heatmap_adaptive_std_multiplier * h_std
        else:
            threshold = cfg.heatmap_threshold_fixed

        # 2. Binary threshold + morphological cleanup
        binary = (heatmap > threshold).astype(np.uint8)
        if cfg.open_kernel_size > 0:
            kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                                     (cfg.open_kernel_size, cfg.open_kernel_size))
            binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_open)
        if cfg.close_kernel_size > 0:
            kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                                      (cfg.close_kernel_size, cfg.close_kernel_size))
            binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel_close)

        # 3. Connected components
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
            binary, connectivity=8)

        components = []
        for i in range(1, num_labels):
            area = int(stats[i, cv2.CC_STAT_AREA])
            if area < cfg.min_component_area:
                continue
            x, y, w, h = stats[i, cv2.CC_STAT_LEFT], stats[i, cv2.CC_STAT_TOP], \
                         stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]

            # Solidity filter
            component_mask = (labels == i).astype(np.uint8)
            hull = cv2.convexHull(cv2.findNonZero(component_mask))
            hull_area = cv2.contourArea(hull) if hull is not None else area
            solidity = area / hull_area if hull_area > 0 else 0.0
            if solidity < cfg.min_solidity:
                continue

            patch_score = float(heatmap[component_mask > 0].mean()) if area > 0 else 0.0
            components.append((area, solidity, patch_score, x, y, w, h))

        if not components:
            return []

        # Sort by area * score descending
        components.sort(key=lambda c: c[0] * c[2], reverse=True)
        components = components[:cfg.max_proposals]

        roi_h, roi_w = roi_image.shape[:2]
        roi_context = ROIContext(
            roi_bbox=BoundingBox(*roi_bbox),
            roi_image_ref=ImageRef(key=roi_image_key or f"roi/{uuid.uuid4().hex[:8]}.jpg",
                                   width=roi_w, height=roi_h),
            roi_size=(roi_w, roi_h),
        )

        proposals: list[PatchProposal] = []
        for rank, (area, solidity, pscore, x, y, w, h) in enumerate(components):
            # Expand bbox with context padding
            pad_w = int(w * cfg.context_padding_ratio)
            pad_h = int(h * cfg.context_padding_ratio)
            x1 = max(0, x - pad_w)
            y1 = max(0, y - pad_h)
            x2 = min(roi_w, x + w + pad_w)
            y2 = min(roi_h, y + h + pad_h)

            if (x2 - x1) < cfg.min_crop_size or (y2 - y1) < cfg.min_crop_size:
                continue

            pid = uuid.uuid4().hex[:12]
            patch_bbox = BoundingBox(float(x1), float(y1), float(x2), float(y2))

            # Build feature refs
            feat_prefix = f"features/{isolation_key.replace('|', '/')}/{pid}"
            ead_feats = EfficientADFeatures(
                teacher_l1_ref=f"{feat_prefix}/teacher_l1.npy" if efficientad_features else "",
                teacher_l2_ref=f"{feat_prefix}/teacher_l2.npy" if efficientad_features else "",
                teacher_l3_ref=f"{feat_prefix}/teacher_l3.npy" if efficientad_features else "",
                difference_ref=f"{feat_prefix}/difference.npy" if efficientad_features else "",
            )

            anomaly_ctx = AnomalyContext(
                anomaly_score=pscore,
                anomaly_threshold=anomaly_threshold,
                heatmap_ref=ImageRef(key=f"{feat_prefix}/heatmap.png"),
                feature_ref=feat_prefix,
            )

            proposals.append(PatchProposal(
                proposal_id=pid,
                isolation_key=isolation_key,
                source_roi=roi_context,
                patch_image=ImageRef(key=f"{feat_prefix}/patch.png",
                                     width=x2 - x1, height=y2 - y1),
                patch_bbox=patch_bbox,
                anomaly_context=anomaly_ctx,
                efficientad_features=ead_feats,
                proposal_metadata=ProposalMetadata(
                    component_area=area,
                    component_solidity=solidity,
                    rank=rank + 1,
                    total_proposals=len(components),
                    generation_params={
                        "threshold": threshold,
                        "threshold_mode": cfg.heatmap_threshold_mode,
                    },
                ),
            ))

        return proposals

    def extract_patch_crops(self, roi_image: np.ndarray,
                            proposals: list[PatchProposal]) -> list[np.ndarray]:
        """Extract image crops for each proposal from the ROI image."""
        crops = []
        for p in proposals:
            b = p.patch_bbox
            crop = roi_image[int(b.y1):int(b.y2), int(b.x1):int(b.x2)]
            crops.append(crop)
        return crops

    def extract_patch_features(self, efficientad_features: dict[str, np.ndarray],
                               proposals: list[PatchProposal],
                               roi_size: tuple[int, int]) -> list[dict[str, np.ndarray]]:
        """Extract EfficientAD features for each proposal's spatial region."""
        roi_h, roi_w = roi_size
        patch_features = []
        for p in proposals:
            b = p.patch_bbox
            # Scale feature coordinates to feature map dimensions
            pf: dict[str, np.ndarray] = {}
            for key, feat_map in efficientad_features.items():
                if feat_map.ndim < 2:
                    continue
                fh, fw = feat_map.shape[0], feat_map.shape[1]
                fx1 = max(0, int(b.x1 * fw / roi_w))
                fy1 = max(0, int(b.y1 * fh / roi_h))
                fx2 = min(fw, int(b.x2 * fw / roi_w))
                fy2 = min(fh, int(b.y2 * fh / roi_h))
                if fx2 <= fx1 or fy2 <= fy1:
                    continue
                pf[key] = feat_map[fy1:fy2, fx1:fx2]
            patch_features.append(pf)
        return patch_features
```

- [ ] **Step 4: Create `seat_defect_core/proposal/aggregation.py`**

```python
from __future__ import annotations

import numpy as np

from defect_protocol import FilterResult, PatchProposal


def aggregate_proposals(proposals: list[PatchProposal],
                        method: str = "weighted_confidence",
                        area_exponent: float = 0.5,
                        confidence_threshold: float = 0.5) -> FilterResult | None:
    """Aggregate per-patch filter results into a single ROI-level decision."""
    valid = [p for p in proposals if p.filter_result is not None]
    if not valid:
        return None

    if method == "max_confidence":
        best = max(valid, key=lambda p: p.filter_result.confidence)
        return best.filter_result

    if method == "weighted_confidence":
        weights = []
        confidences = []
        real_scores = []
        false_scores = []
        for p in valid:
            area = p.proposal_metadata.component_area
            score = p.anomaly_context.anomaly_score
            w = (area ** area_exponent) * score
            weights.append(w)
            confidences.append(p.filter_result.confidence)
            real_scores.append(p.filter_result.real_defect_score)
            false_scores.append(p.filter_result.false_alarm_score)

        w_sum = sum(weights)
        if w_sum == 0:
            return None
        weights_norm = [w / w_sum for w in weights]

        weighted_confidence = sum(w * c for w, c in zip(weights_norm, confidences))
        weighted_real = sum(w * r for w, r in zip(weights_norm, real_scores))
        weighted_false = sum(w * f for w, f in zip(weights_norm, false_scores))

        return FilterResult(
            is_real_defect=weighted_confidence >= confidence_threshold,
            confidence=weighted_confidence,
            real_defect_score=weighted_real,
            false_alarm_score=weighted_false,
            class_id=1 if weighted_confidence >= confidence_threshold else 0,
            diagnostics={
                "num_proposals": len(valid),
                "max_confidence": float(max(confidences)),
                "min_confidence": float(min(confidences)),
                "aggregation_method": method,
            },
        )

    return None
```

- [ ] **Step 5: Commit**

```bash
git add seat_defect_core/proposal/
git commit -m "feat: add region proposal generation and aggregation modules"
```

---

### Task 9: Add ProposalConfig to seat_defect_core config

**Files:**
- Modify: `seat_defect_core/config.py`

- [ ] **Step 1: Add `ProposalConfig` import and `FilterClassifierConfig` input_size update**

Add import at top:
```python
from .proposal.config import ProposalConfig  # noqa: F401
```

Update `FilterClassifierConfig.input_size` default (line 68):
```python
    input_size: int = 448  # was 224
```

Add `ProposalConfig` field to `CameraConfig` after `rule_engine` (line 168):
```python
    proposal: ProposalConfig | None = None
```

- [ ] **Step 2: Commit**

```bash
git add seat_defect_core/config.py
git commit -m "feat: add ProposalConfig to seat_defect_core config hierarchy"
```

---

### Task 10: Upgrade FilterClassifierService for dual-modal inference

**Files:**
- Modify: `seat_defect_core/classifier/engine.py`

- [ ] **Step 1: Add `predict_dual_modal` method to `FilterClassifierService`**

Add new method after `predict()` (after line 128):

```python
    def predict_dual_modal(
        self, patch_image: np.ndarray,
        ead_features: dict[str, np.ndarray] | None = None,
    ) -> FilterClassifierResult:
        """Predict with dual-modal input: patch image + EfficientAD features."""
        if self._model is None:
            return FilterClassifierResult(
                is_real_defect=True, confidence=0.0,
                real_defect_score=0.0, false_alarm_score=0.0,
                class_id=1,
                diagnostics={"mode": "fallback_no_model", "reason": "model not loaded"},
            )

        try:
            import torch

            # Preprocess image
            rgb = cv2.cvtColor(patch_image, cv2.COLOR_BGR2RGB)
            resized = cv2.resize(rgb, (self.config.input_size, self.config.input_size))
            tensor = torch.from_numpy(resized).permute(2, 0, 1).float() / 255.0
            tensor = (tensor - torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)) / \
                     torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)
            tensor = tensor.unsqueeze(0).to(self._device)

            # Preprocess features
            feat_tensors = None
            if ead_features is not None:
                feat_tensors = {}
                for key in ["teacher_l1", "teacher_l2", "teacher_l3", "difference"]:
                    if key in ead_features:
                        arr = ead_features[key]
                        t = torch.from_numpy(arr).float().to(self._device)
                        if t.dim() == 3:
                            t = t.permute(2, 0, 1).unsqueeze(0)  # HWC -> 1CHW
                        elif t.dim() == 4:
                            t = t.permute(0, 3, 1, 2)  # NHWC -> NCHW
                        feat_tensors[key] = t

            with torch.no_grad():
                logits = self._model(tensor, feat_tensors if feat_tensors else None)

            probs = torch.softmax(logits, dim=1)[0]
            false_alarm_score = float(probs[0].cpu())
            real_defect_score = float(probs[1].cpu())
            class_id = int(torch.argmax(probs).cpu())
            confidence = float(probs[class_id].cpu())
            is_real_defect = class_id == 1 and confidence >= self.config.confidence_threshold

            return FilterClassifierResult(
                is_real_defect=is_real_defect,
                confidence=confidence,
                real_defect_score=real_defect_score,
                false_alarm_score=false_alarm_score,
                class_id=class_id,
                diagnostics={"mode": "dual_modal"},
            )
        except Exception:
            import traceback
            traceback.print_exc()
            return FilterClassifierResult(
                is_real_defect=True, confidence=0.0,
                real_defect_score=0.0, false_alarm_score=0.0,
                class_id=1,
                diagnostics={"mode": "error_fallback", "reason": "inference failed"},
            )
```

- [ ] **Step 2: Commit**

```bash
git add seat_defect_core/classifier/engine.py
git commit -m "feat: add predict_dual_modal to FilterClassifierService for dual-modal inference"
```

---

### Task 11: Integrate proposal + filter into inspection_camera.py

**Files:**
- Modify: `seat_defect_core/service/inspection_camera.py`

- [ ] **Step 1: Add imports at top of `inspection_camera.py`**

After existing imports, add:
```python
from ..proposal import ProposalGenerator, ProposalConfig, aggregate_proposals
from ..classifier.engine import FilterClassifierService
from defect_protocol import FilterResult
```

- [ ] **Step 2: Add proposal + filter logic in `inspect_prepared_camera`**

After the texture_result check (after line 160, before building CameraInspectionResult):

```python
        # --- Region Proposal + Dual-Modal Filter ---
        filter_result: Optional[FilterResult] = None
        proposals: list[Any] = []

        if texture_result.is_anomaly:
            filter_service = getattr(service, '_filter_service', None)
            if filter_service is not None:
                try:
                    proposal_cfg = camera.proposal or ProposalConfig()
                    generator = ProposalGenerator(proposal_cfg)
                    isolation_key = f"{seat_model_id or 'unknown'}|{camera.camera_id}|default"

                    roi_h, roi_w = prepared.roi.aligned_roi_image.shape[:2]
                    roi_bbox = (
                        int(prepared.roi.crop_box.x1) if prepared.roi.crop_box else 0,
                        int(prepared.roi.crop_box.y1) if prepared.roi.crop_box else 0,
                        roi_w, roi_h,
                    )

                    proposals = generator.generate(
                        heatmap=texture_result.anomaly_map,
                        roi_image=prepared.roi.aligned_roi_image,
                        efficientad_features=texture_result.features,
                        anomaly_score=texture_result.score,
                        anomaly_threshold=texture_result.threshold,
                        roi_bbox=roi_bbox,
                        isolation_key=isolation_key,
                    )

                    # Per-patch dual-modal inference
                    patch_crops = generator.extract_patch_crops(
                        prepared.roi.aligned_roi_image, proposals)
                    patch_features_list = []
                    if texture_result.features:
                        patch_features_list = generator.extract_patch_features(
                            texture_result.features, proposals,
                            (roi_h, roi_w))

                    for i, proposal in enumerate(proposals):
                        patch_img = patch_crops[i] if i < len(patch_crops) else None
                        patch_feats = patch_features_list[i] if i < len(patch_features_list) else None
                        if patch_img is not None:
                            pf_result = filter_service.predict_dual_modal(
                                patch_img, patch_feats)
                            proposal.filter_result = pf_result

                    # Aggregate
                    filter_result = aggregate_proposals(proposals)
                except Exception:
                    import traceback
                    traceback.print_exc()
                    filter_result = FilterResult(
                        is_real_defect=True, confidence=0.0,
                        real_defect_score=0.0, false_alarm_score=0.0,
                        class_id=1, diagnostics={"mode": "error_fallback"},
                    )

        # Update status with filter result
        if filter_result is not None and not filter_result.is_real_defect:
            status = "OK"
            reason = "filter_suppressed"
```

- [ ] **Step 3: Pass proposals and filter_result to CameraInspectionResult**

Update the CameraInspectionResult construction to include:
```python
        filter_result=filter_result,
        # proposals field added to CameraInspectionResult (Task 12)
```

- [ ] **Step 4: Commit**

```bash
git add seat_defect_core/service/inspection_camera.py
git commit -m "feat: integrate region proposal and dual-modal filter into inspection pipeline"
```

---

### Task 12: Add proposals field to CameraInspectionResult

**Files:**
- Modify: `seat_defect_core/core_types/results.py:107-170`

- [ ] **Step 1: Add `proposals` field**

After `filter_result` field (line 144), add:
```python
    proposals: list[Any] = field(default_factory=list)  # list[PatchProposal]
```

- [ ] **Step 2: Commit**

```bash
git add seat_defect_core/core_types/results.py
git commit -m "feat: add proposals field to CameraInspectionResult for patch-level results"
```

---

### Task 13: Upgrade anomaly_uploader to handle proposals and features

**Files:**
- Modify: `seat_defect_core/anomaly_uploader.py`

- [ ] **Step 1: Add feature upload logic in `upload_camera_result`**

After the `crop_files` section (after line 131), add feature file uploads:

```python
        # --- Upload EfficientAD feature files (.npy) ---
        feature_files: list[tuple[str, bytes, str]] = []
        texture = result.texture_result
        if texture is not None and texture.features is not None:
            import io as _io
            for feat_name, feat_array in texture.features.items():
                buf = _io.BytesIO()
                np.save(buf, feat_array)
                feature_files.append(
                    (f"{feat_name}.npy", buf.getvalue(), "application/octet-stream")
                )

        # --- Upload proposal patch crops + per-patch features ---
        proposal_files: list[tuple[str, bytes, str]] = []
        for proposal in getattr(result, 'proposals', []):
            pid = proposal.proposal_id
            # We need the actual patch crop - store reference for now
            # Backend will reconstruct from the main anomaly crop
            pass

        # Send feature files alongside crops
        for fname, fdata, ftype in feature_files:
            files.append(("feature_files", (fname, fdata, ftype)))
```

Update the `data` dictionary to include proposals JSON:
```python
        if result.proposals:
            from defect_protocol import proposals_to_json
            data["proposals_json"] = proposals_to_json(result.proposals)
```

- [ ] **Step 2: Commit**

```bash
git add seat_defect_core/anomaly_uploader.py
git commit -m "feat: upload EfficientAD features and proposals JSON in anomaly uploader"
```

---

### Task 14: Update backend anomaly schema for proposals

**Files:**
- Modify: `backend/app/schemas/anomaly.py`

- [ ] **Step 1: Add proposals field to upload schema**

The upload endpoint receives form data, not JSON body. Add helper parsing:
```python
class AnomalyUploadMetadata(BaseModel):
    """Parsed from form data for upload-with-files endpoint."""
    proposals_json: str | None = None
    feature_count: int = 0
```

Add to `AnomalyResponse`:
```python
    proposal_count: int = 0
    proposals_json: str | None = None
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/anomaly.py
git commit -m "feat: add proposals fields to anomaly schemas"
```

---

### Task 15: Upgrade AnomalyService for proposal + feature storage

**Files:**
- Modify: `backend/app/services/anomaly/service.py`

- [ ] **Step 1: Add proposals_json and feature_files to `create_anomaly_with_files`**

Add parameters:
```python
    proposals_json: str | None = None,
    feature_files: list[bytes] | None = None,
```

Store features in MinIO under the anomaly's base path:
```python
        if feature_files:
            feature_dir = f"{base_path}/features"
            for i, feat_data in enumerate(feature_files):
                _save(feat_data, f"{feature_dir}/feature_{i:03d}.npy",
                      "application/octet-stream")
```

Store proposals_json as metadata on the AnomalyRecord (or in a separate file):
```python
        if proposals_json:
            _save(proposals_json.encode("utf-8"), f"{base_path}/proposals.json",
                  "application/json")
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/anomaly/service.py
git commit -m "feat: store EfficientAD features and proposals in anomaly service"
```

---

### Task 16: Replace FilterClassifierTrainer with DualModalTrainer in Celery worker

**Files:**
- Modify: `backend/app/workers/training_worker/tasks.py`

- [ ] **Step 1: Replace `train_filter_classifier` Celery task**

Replace the import from `ml.classifier.trainer import FilterClassifierTrainer` with:
```python
from ml.classifier.dual_modal import DualModalTrainer, DualModalConfig
```

Replace the trainer instantiation:
```python
    config = DualModalConfig(
        num_classes=num_classes,
        image_size=448,
        learning_rate=learning_rate,
        image_branch_lr=learning_rate * 0.1,
        batch_size=batch_size,
        epochs=epochs,
        early_stopping_patience=10,
        class_names=class_names or ["false_alarm", "real_defect"],
        output_dir=output_dir,
    )
    trainer = DualModalTrainer(config=config, device=device)
```

Replace `_ImageDataset` with `DualModalDataset`:
```python
    train_dataset = DualModalDataset(
        images=train_images, labels=train_labels,
        features_dir=features_dir, proposal_ids=train_proposal_ids,
        image_size=448, augment=augmentations,
    )
    val_dataset = DualModalDataset(
        images=val_images, labels=val_labels,
        features_dir=features_dir, proposal_ids=val_proposal_ids,
        image_size=448, augment=False,
    )
```

- [ ] **Step 2: Update `_load_training_data` to return proposal_ids and features_dir**

Add proposal-level loading:
```python
    async def _load_training_data(...) -> tuple[list[np.ndarray], list[int], list[str], str | None]:
        # ... existing logic ...
        # Additionally track proposal_ids and features_dir from MinIO paths
        return images, labels, proposal_ids, features_dir
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/workers/training_worker/tasks.py
git commit -m "feat: replace FilterClassifierTrainer with DualModalTrainer in training worker"
```

---

### Task 17: Remove old FilterClassifierTrainer

**Files:**
- Delete: `ml/classifier/trainer.py`

- [ ] **Step 1: Delete the old trainer**

```bash
rm ml/classifier/trainer.py
```

- [ ] **Step 2: Verify no remaining imports of the old trainer**

```bash
grep -r "FilterClassifierTrainer" ml/ backend/ seat_defect_core/ || echo "No remaining references"
```

Expected: `No remaining references`

- [ ] **Step 3: Commit**

```bash
git add ml/classifier/trainer.py
git commit -m "refactor: remove deprecated FilterClassifierTrainer, replaced by DualModalTrainer"
```

---

### Task 18: Update serialization.py in seat_defect_core

**Files:**
- Modify: `seat_defect_core/serialization.py`

- [ ] **Step 1: Add proposals serialization**

In the camera result serialization function, add:
```python
    if camera.proposals:
        from defect_protocol import proposals_to_json
        result["proposals"] = json.loads(proposals_to_json(camera.proposals))
```

- [ ] **Step 2: Commit**

```bash
git add seat_defect_core/serialization.py
git commit -m "feat: add proposals serialization to inspection result output"
```

---

### Task 19: Register defect_protocol as dependency

**Files:**
- Modify: `seat_defect_core/pyproject.toml`
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Add defect_protocol dependency to both pyproject.toml files**

```toml
[project]
dependencies = [
    # ... existing ...
    "defect_protocol",
]

[tool.uv.sources]
defect_protocol = { path = "../defect_protocol", editable = true }
```

- [ ] **Step 2: Sync dependencies**

```bash
cd seat_defect_core && uv sync
cd ../backend && uv sync
```

- [ ] **Step 3: Commit**

```bash
git add seat_defect_core/pyproject.toml backend/pyproject.toml
git commit -m "feat: add defect_protocol as editable dependency to both components"
```

---

### Task 20: End-to-end integration verification

- [ ] **Step 1: Verify defect_protocol imports**

```bash
cd seat_defect_core && uv run python -c "from defect_protocol import PatchProposal, proposals_to_json; print('seat_defect_core OK')"
cd ../backend && uv run python -c "from defect_protocol import PatchProposal, proposals_from_json; print('backend OK')"
```

Expected: `seat_defect_core OK` and `backend OK`

- [ ] **Step 2: Run all existing tests**

```bash
cd backend && uv run pytest -v
```

- [ ] **Step 3: Verify types**

```bash
cd backend && uv run mypy app
```

- [ ] **Step 4: Commit any final fixes**

```bash
git add -A && git diff --cached --stat
git commit -m "chore: final integration fixes and verification"
```
