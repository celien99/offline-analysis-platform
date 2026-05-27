# Calibration Layer + Cascading Budget 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 `calibration/` 模块实现跨机位特征校准（EMA Feature Center + Camera Normalization + Projector + Whitening），并扩展 `BudgetController` 为两级预算控制器（Proposal + Filter 级联）。

**Architecture:** calibration 作为独立模块与 proposal/tracking 平级。CascadingBudgetController 包装现有 BudgetController，新增 `schedule_filter()` 方法。CalibrationRegistry 作为统一入口在 `InspectionService` 中初始化，在 `inspect_prepared_camera` 中接入 pipeline。

**Tech Stack:** Python 3.11+, numpy, PyTorch, dataclasses

---

## 文件结构

```
Create:
  seat_defect_core/calibration/__init__.py
  seat_defect_core/calibration/config.py
  seat_defect_core/calibration/camera_normalizer.py
  seat_defect_core/calibration/projector.py
  seat_defect_core/calibration/whitening.py
  seat_defect_core/calibration/feature_center.py
  seat_defect_core/calibration/registry.py
  seat_defect_core/tests/__init__.py
  seat_defect_core/tests/test_calibration.py

Modify:
  seat_defect_core/proposal/config.py        # 新增 CascadingBudgetConfig
  seat_defect_core/proposal/budget.py         # 新增 CascadingBudgetController
  seat_defect_core/proposal/__init__.py       # 导出新类型
  seat_defect_core/config.py                  # CameraConfig 增加 calibration 字段
  seat_defect_core/service/core.py            # InspectionService 持有 CalibrationRegistry
  seat_defect_core/service/inspection_camera.py  # 接入 calibration + cascading budget
```

---

### Task 1: 创建 calibration 模块骨架和配置

**Files:**
- Create: `seat_defect_core/calibration/__init__.py`
- Create: `seat_defect_core/calibration/config.py`

- [ ] **Step 1: 创建 `calibration/config.py`**

```python
"""Calibration layer configuration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CameraNormConfig:
    """Per-camera normalization settings."""
    enabled: bool = True
    stats_path: str = ""  # 预计算的 mean/std .npz 文件路径


@dataclass
class ProjectionConfig:
    """Embedding projection settings."""
    enabled: bool = True
    projector_path: str = ""  # 投影矩阵 .npz 文件路径


@dataclass
class WhiteningConfig:
    """ZCA/PCA whitening settings."""
    enabled: bool = True
    method: str = "zca"  # "zca" | "pca"
    regularization: float = 1e-4
    matrix_path: str = ""  # 预计算的白化矩阵 .npz 文件路径


@dataclass
class EMACenterConfig:
    """EMA feature center tracking settings."""
    enabled: bool = True
    alpha: float = 0.99  # EMA 衰减系数
    min_samples: int = 10  # 建立有效中心的最小样本数
    novelty_threshold: float = 0.3  # is_novel 的距离阈值
    centers_path: str = ""  # 预存中心文件的路径


@dataclass
class CalibrationConfig:
    """Feature calibration layer top-level config."""
    enabled: bool = True

    camera_norm: CameraNormConfig = field(default_factory=CameraNormConfig)
    projection: ProjectionConfig = field(default_factory=ProjectionConfig)
    whitening: WhiteningConfig = field(default_factory=WhiteningConfig)
    ema_center: EMACenterConfig = field(default_factory=EMACenterConfig)
```

- [ ] **Step 2: 创建 `calibration/__init__.py`**

```python
"""Feature calibration layer — cross-camera feature normalization, projection, and center tracking."""

from __future__ import annotations

from .config import (
    CalibrationConfig,
    CameraNormConfig,
    EMACenterConfig,
    ProjectionConfig,
    WhiteningConfig,
)

__all__ = [
    "CalibrationConfig",
    "CameraNormConfig",
    "EMACenterConfig",
    "ProjectionConfig",
    "WhiteningConfig",
]
```

- [ ] **Step 3: Commit**

```bash
git add seat_defect_core/calibration/
git commit -m "feat(calibration): 创建 calibration 模块骨架和配置定义"
```

---

### Task 2: 实现 CameraNormalizer

**Files:**
- Create: `seat_defect_core/calibration/camera_normalizer.py`

- [ ] **Step 1: 实现 CameraNormalizer**

```python
"""Per-camera per-channel feature normalization."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np


@dataclass
class CameraNormStats:
    """Per-channel mean/std for a single feature key."""
    mean: np.ndarray  # shape matches feature channels
    std: np.ndarray
    sample_count: int = 0
    # For online incremental update (Welford's algorithm)
    _M2: Optional[np.ndarray] = None

    def to_dict(self) -> dict:
        return {
            "mean": self.mean,
            "std": self.std,
            "sample_count": self.sample_count,
        }


class CameraNormalizer:
    """Per-camera per-channel (x - mean) / std normalization for EfficientAD features.

    每个 (camera_id, model_path) 对应一组独立的 stats。
    四个特征 key 各存一组：teacher_l1, teacher_l2, teacher_l3, difference。

    离线拟合：在正常样本（is_anomaly=False）的特征上调用 fit()。
    推理时：调用 normalize() 查表应用，零额外开销。
    """

    _FEATURE_KEYS = ("teacher_l1", "teacher_l2", "teacher_l3", "difference")

    def __init__(self):
        self._stats: dict[str, CameraNormStats] = {}

    def fit(self, features_list: list[dict[str, np.ndarray]]) -> None:
        """在正常样本特征列表上离线拟合 per-channel mean/std。

        Args:
            features_list: 正常样本的特征字典列表，每个字典含 'teacher_l1' 等 key，
                          每个 value 是 (H, W, C) 或 (C,) 的 numpy 数组。
        """
        accumulators: dict[str, list[np.ndarray]] = {key: [] for key in self._FEATURE_KEYS}
        for feats in features_list:
            for key in self._FEATURE_KEYS:
                val = feats.get(key)
                if val is not None:
                    # 展平 spatial 维度，保留 channel 维度
                    if val.ndim >= 3:
                        flat = val.reshape(-1, val.shape[-1]).astype(np.float64)
                    elif val.ndim == 2:
                        flat = val.astype(np.float64)
                    else:
                        flat = val.reshape(1, -1).astype(np.float64)
                    accumulators[key].append(flat)

        for key in self._FEATURE_KEYS:
            samples = accumulators[key]
            if not samples:
                continue
            all_data = np.concatenate(samples, axis=0)
            mean = all_data.mean(axis=0)
            std = all_data.std(axis=0)
            std = np.where(std < 1e-8, 1.0, std)  # 防止除零
            self._stats[key] = CameraNormStats(
                mean=mean.astype(np.float32),
                std=std.astype(np.float32),
                sample_count=all_data.shape[0],
            )

    def normalize(self, features: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        """对特征做 per-channel 标准化。缺失 key 保持原值。"""
        result: dict[str, np.ndarray] = {}
        for key in self._FEATURE_KEYS:
            val = features.get(key)
            if val is None:
                continue
            stats = self._stats.get(key)
            if stats is None:
                result[key] = val.copy()
            else:
                # broadcast: mean/std shape 匹配 val 最后一维
                result[key] = (val.astype(np.float32) - stats.mean) / stats.std
        return result

    def update(self, features: dict[str, np.ndarray]) -> None:
        """在线增量更新 stats（Welford 算法）。仅在正常判定时调用。"""
        for key in self._FEATURE_KEYS:
            val = features.get(key)
            if val is None:
                continue
            if val.ndim >= 3:
                samples = val.reshape(-1, val.shape[-1]).astype(np.float64)
            elif val.ndim == 2:
                samples = val.astype(np.float64)
            else:
                samples = val.reshape(1, -1).astype(np.float64)

            batch_mean = samples.mean(axis=0)
            batch_count = samples.shape[0]

            existing = self._stats.get(key)
            if existing is None:
                self._stats[key] = CameraNormStats(
                    mean=batch_mean.astype(np.float32),
                    std=samples.std(axis=0).astype(np.float32),
                    sample_count=batch_count,
                )
                continue

            # Welford 合并
            delta = batch_mean - existing.mean
            new_count = existing.sample_count + batch_count
            existing.mean = existing.mean + delta * batch_count / new_count
            # std 使用合并后的均值重新估计（近似）
            existing.std = np.sqrt(
                (existing.std ** 2 * existing.sample_count
                 + (samples.var(axis=0) * batch_count
                    + delta ** 2 * existing.sample_count * batch_count / new_count))
                / new_count
            ).astype(np.float32)
            existing.std = np.where(existing.std < 1e-8, 1.0, existing.std)
            existing.sample_count = new_count

    def save(self, path: str) -> None:
        """保存 stats 到 .npz 文件。"""
        data: dict[str, np.ndarray] = {}
        for key, stats in self._stats.items():
            data[f"{key}_mean"] = stats.mean
            data[f"{key}_std"] = stats.std
            data[f"{key}_count"] = np.array(stats.sample_count)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, **data)

    @classmethod
    def load(cls, path: str) -> "CameraNormalizer":
        """从 .npz 文件加载 stats。"""
        data = np.load(path)
        normalizer = cls()
        for key in cls._FEATURE_KEYS:
            mean_key = f"{key}_mean"
            if mean_key in data:
                normalizer._stats[key] = CameraNormStats(
                    mean=data[mean_key].astype(np.float32),
                    std=data[f"{key}_std"].astype(np.float32),
                    sample_count=int(data.get(f"{key}_count", 0)),
                )
        return normalizer

    @property
    def is_fitted(self) -> bool:
        return len(self._stats) > 0

    @property
    def fitted_keys(self) -> list[str]:
        return list(self._stats.keys())
```

- [ ] **Step 2: Commit**

```bash
git add seat_defect_core/calibration/camera_normalizer.py
git commit -m "feat(calibration): 实现 CameraNormalizer — 机位级 per-channel 标准化"
```

---

### Task 3: 实现 EmbeddingProjector

**Files:**
- Create: `seat_defect_core/calibration/projector.py`

- [ ] **Step 1: 实现 EmbeddingProjector**

```python
"""Project EfficientAD multi-scale features to 384-dim unified embedding space."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np


@dataclass
class ProjectionParams:
    """Precomputed projection parameters."""
    weights: np.ndarray       # (concat_dim, output_dim)
    bias: np.ndarray          # (output_dim,)
    pool_sizes: dict[str, tuple[int, int]]  # per-key adaptive pool target (H, W)
    input_keys: list[str]     # ordered keys for concatenation


class EmbeddingProjector:
    """EfficientAD 多尺度特征图 → 384-dim L2 归一化 UnifiedEmbedding。

    流程：
    1. 各尺度 feature map → adaptive average pool → 固定尺寸向量
    2. 按 input_keys 顺序 concat
    3. y = concat_vec @ weights + bias
    4. y / ||y||_2 → 输出 384-dim L2 归一化向量

    投影矩阵离线训练（PCA 初始化 + linear probe finetune）后存为 .npz。
    """

    def __init__(self):
        self._params: Optional[ProjectionParams] = None

    def project(self, features: dict[str, np.ndarray]) -> np.ndarray:
        """将特征字典投影到 384-dim L2 归一化向量。

        Returns:
            (384,) float32 numpy array, L2 norm ≈ 1.0
        """
        if self._params is None:
            raise RuntimeError("Projector not fitted or loaded")

        pooled_vecs = []
        for key in self._params.input_keys:
            feat = features.get(key)
            if feat is None:
                raise KeyError(f"Missing feature key '{key}' for projection")
            pooled = self._adaptive_pool(feat, self._params.pool_sizes[key])
            pooled_vecs.append(pooled)

        concat = np.concatenate(pooled_vecs)
        y = concat @ self._params.weights + self._params.bias
        norm = np.linalg.norm(y)
        if norm > 1e-8:
            y = y / norm
        return y.astype(np.float32)

    @staticmethod
    def _adaptive_pool(feature_map: np.ndarray, target_size: tuple[int, int]) -> np.ndarray:
        """Spatial adaptive average pool for a single feature map.

        Args:
            feature_map: (H, W, C) array
            target_size: (out_h, out_w) — 通常 (1,1) 做全局 pooling

        Returns:
            (channels * out_h * out_w,) flattened vector
        """
        h, w, c = feature_map.shape
        out_h, out_w = target_size

        # 简单分块平均 = adaptive average pool 的等效实现
        result = np.zeros((out_h, out_w, c), dtype=np.float32)
        for i in range(out_h):
            for j in range(out_w):
                y1 = int(i * h / out_h)
                y2 = int((i + 1) * h / out_h)
                x1 = int(j * w / out_w)
                x2 = int((j + 1) * w / out_w)
                result[i, j] = feature_map[y1:y2, x1:x2].mean(axis=(0, 1))
        return result.ravel()

    def save(self, path: str) -> None:
        """保存投影参数到 .npz 文件。"""
        if self._params is None:
            raise RuntimeError("No projection params to save")
        data: dict[str, np.ndarray] = {
            "weights": self._params.weights,
            "bias": self._params.bias,
            "input_keys": np.array(self._params.input_keys),
        }
        for key, size in self._params.pool_sizes.items():
            data[f"pool_{key}_h"] = np.array(size[0])
            data[f"pool_{key}_w"] = np.array(size[1])
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, **data)

    @classmethod
    def load(cls, path: str) -> "EmbeddingProjector":
        """从 .npz 文件加载投影参数。"""
        data = np.load(path, allow_pickle=True)
        instance = cls()
        input_keys = list(data["input_keys"])
        pool_sizes: dict[str, tuple[int, int]] = {}
        for key in input_keys:
            h = int(data.get(f"pool_{key}_h", 1))
            w = int(data.get(f"pool_{key}_w", 1))
            pool_sizes[key] = (h, w)
        instance._params = ProjectionParams(
            weights=data["weights"].astype(np.float32),
            bias=data["bias"].astype(np.float32),
            pool_sizes=pool_sizes,
            input_keys=input_keys,
        )
        return instance

    @classmethod
    def fit(
        cls,
        features_list: list[dict[str, np.ndarray]],
        *,
        output_dim: int = 384,
        pool_sizes: Optional[dict[str, tuple[int, int]]] = None,
    ) -> "EmbeddingProjector":
        """用 PCA 初始化投影矩阵。

        从正常样本的多尺度特征计算 PCA 投影到 output_dim 维。
        pool_sizes 默认为全局平均池化 (1, 1)。
        """
        if not features_list:
            raise ValueError("features_list must not be empty")

        # 确定 input_keys
        first = features_list[0]
        input_keys = sorted(k for k in first if isinstance(first[k], np.ndarray) and first[k].ndim >= 3)

        if pool_sizes is None:
            pool_sizes = {key: (1, 1) for key in input_keys}

        # 收集所有池化后的向量
        pooled_list = []
        instance = cls()
        for feats in features_list:
            pooled = []
            for key in input_keys:
                feat = feats.get(key)
                if feat is None:
                    pooled.append(np.zeros(
                        sum(pool_sizes[key]) * 1, dtype=np.float32))
                else:
                    pooled.append(instance._adaptive_pool(feat, pool_sizes[key]))
            pooled_list.append(np.concatenate(pooled))

        X = np.stack(pooled_list, axis=0).astype(np.float64)  # (N, concat_dim)
        mean_vec = X.mean(axis=0)
        X_centered = X - mean_vec

        # PCA via SVD
        U, S, Vt = np.linalg.svd(X_centered, full_matrices=False)
        k = min(output_dim, X_centered.shape[1], X_centered.shape[0])
        weights = Vt[:k].T  # (concat_dim, output_dim)
        bias = -mean_vec @ weights

        instance._params = ProjectionParams(
            weights=weights.astype(np.float32),
            bias=bias.astype(np.float32),
            pool_sizes=pool_sizes,
            input_keys=input_keys,
        )
        return instance

    @property
    def is_fitted(self) -> bool:
        return self._params is not None

    @property
    def output_dim(self) -> int:
        if self._params is None:
            return 0
        return self._params.weights.shape[1]
```

- [ ] **Step 2: Commit**

```bash
git add seat_defect_core/calibration/projector.py
git commit -m "feat(calibration): 实现 EmbeddingProjector — 多尺度特征投影到 384-dim"
```

---

### Task 4: 实现 WhiteningTransform

**Files:**
- Create: `seat_defect_core/calibration/whitening.py`

- [ ] **Step 1: 实现 WhiteningTransform**

```python
"""ZCA / PCA whitening for unified embeddings."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np


class WhiteningTransform:
    """ZCA 白化变换：W = U @ diag(1/sqrt(S + eps)) @ U^T

    在 EmbeddingProjector 之后使用，消除 embedding 维度间的相关性，
    使各维度等方差。只有在统一嵌入空间中白化矩阵才有意义（维度固定，语义对齐）。

    在正常样本的 embedding 上拟合，推理时应用固定矩阵变换。
    """

    def __init__(self, dim: int = 384, regularization: float = 1e-4):
        self._dim = dim
        self._regularization = regularization
        self._W: Optional[np.ndarray] = None  # (dim, dim) whitening matrix
        self._mean: Optional[np.ndarray] = None  # (dim,) embedding mean

    def fit(self, embeddings: list[np.ndarray]) -> None:
        """在正常样本 embedding 上计算 ZCA/PCA 白化矩阵。

        Args:
            embeddings: 384-dim L2 归一化向量的列表
        """
        X = np.stack(embeddings, axis=0).astype(np.float64)  # (N, dim)
        self._mean = X.mean(axis=0).astype(np.float32)

        X_centered = X - self._mean.astype(np.float64)
        cov = (X_centered.T @ X_centered) / (X.shape[0] - 1)

        # SVD of covariance matrix
        U, S, _ = np.linalg.svd(cov)
        # ZCA: W = U @ diag(1/sqrt(S + eps)) @ U^T
        inv_sqrt = np.diag(1.0 / np.sqrt(S + self._regularization))
        self._W = (U @ inv_sqrt @ U.T).astype(np.float32)

    def whiten(self, embedding: np.ndarray) -> np.ndarray:
        """对单个 embedding 向量应用白化变换。

        Returns:
            白化后的 (dim,) float32 向量
        """
        if self._W is None or self._mean is None:
            raise RuntimeError("WhiteningTransform not fitted")
        x = embedding.astype(np.float32) - self._mean
        whitened = x @ self._W
        # 保持 L2 归一化
        norm = np.linalg.norm(whitened)
        if norm > 1e-8:
            whitened = whitened / norm
        return whitened.astype(np.float32)

    def whiten_batch(self, embeddings: np.ndarray) -> np.ndarray:
        """批量白化。embeddings shape: (N, dim)"""
        if self._W is None or self._mean is None:
            raise RuntimeError("WhiteningTransform not fitted")
        x = embeddings.astype(np.float32) - self._mean.astype(np.float32)
        whitened = x @ self._W
        norms = np.linalg.norm(whitened, axis=1, keepdims=True)
        norms = np.where(norms < 1e-8, 1.0, norms)
        return (whitened / norms).astype(np.float32)

    def save(self, path: str) -> None:
        """保存白化矩阵到 .npz 文件。"""
        if self._W is None or self._mean is None:
            raise RuntimeError("WhiteningTransform not fitted")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, W=self._W, mean=self._mean, dim=self._dim)

    @classmethod
    def load(cls, path: str) -> "WhiteningTransform":
        """从 .npz 文件加载白化矩阵。"""
        data = np.load(path)
        instance = cls(dim=int(data["dim"]))
        instance._W = data["W"].astype(np.float32)
        instance._mean = data["mean"].astype(np.float32)
        return instance

    @property
    def is_fitted(self) -> bool:
        return self._W is not None and self._mean is not None
```

- [ ] **Step 2: Commit**

```bash
git add seat_defect_core/calibration/whitening.py
git commit -m "feat(calibration): 实现 WhiteningTransform — ZCA 白化矩阵"
```

---

### Task 5: 实现 EMAFeatureCenter

**Files:**
- Create: `seat_defect_core/calibration/feature_center.py`

- [ ] **Step 1: 实现 EMAFeatureCenter**

```python
"""EMA-based feature center tracking for defect types."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np


@dataclass
class DefectCenter:
    """单个 defect_type 的 EMA 特征中心。"""
    defect_type: str
    center: np.ndarray           # (dim,) EMA 中心
    sample_count: int
    variance: np.ndarray         # (dim,) 类内方差 EMA
    last_updated: str = ""       # ISO timestamp

    def to_dict(self) -> dict:
        return {
            "defect_type": self.defect_type,
            "center": self.center.tolist(),
            "sample_count": self.sample_count,
            "variance": self.variance.tolist(),
            "last_updated": self.last_updated,
        }


class EMAFeatureCenter:
    """维护所有已知 defect_type 的特征中心 EMA。

    Key: defect_type（跨机位，calibration 之后特征已统一）
    更新：center = alpha * center + (1-alpha) * new_embedding
    方差：variance = alpha * variance + (1-alpha) * (new - center)^2

    用途：
    - Filter Classifier 训练的辅助特征（center_distance）
    - KNN 检索（找与当前 proposal 最相似的已知缺陷）
    - 新缺陷发现（距离所有已知中心都远的 proposal → is_novel）
    """

    def __init__(self, alpha: float = 0.99, dim: int = 384):
        self.alpha = alpha
        self._dim = dim
        self._centers: dict[str, DefectCenter] = {}

    def update(self, defect_type: str, embedding: np.ndarray) -> DefectCenter:
        """用新 embedding 更新 defect_type 的 EMA 中心。
        如果 defect_type 不存在则创建。
        """
        existing = self._centers.get(defect_type)
        if existing is None:
            center = DefectCenter(
                defect_type=defect_type,
                center=embedding.astype(np.float32).copy(),
                sample_count=1,
                variance=np.zeros(self._dim, dtype=np.float32),
                last_updated=datetime.now(timezone.utc).isoformat(),
            )
            self._centers[defect_type] = center
            return center

        existing.center = (
            self.alpha * existing.center + (1.0 - self.alpha) * embedding.astype(np.float32)
        )
        diff = embedding.astype(np.float32) - existing.center
        existing.variance = (
            self.alpha * existing.variance + (1.0 - self.alpha) * (diff * diff)
        )
        existing.sample_count += 1
        existing.last_updated = datetime.now(timezone.utc).isoformat()
        return existing

    def query_nearest(self, embedding: np.ndarray, top_k: int = 5) -> list[tuple[str, float]]:
        """返回距离最近的 top_k 个 defect_type 及余弦距离。"""
        if not self._centers:
            return []
        emb = embedding.astype(np.float32)
        distances = []
        for dtype, center in self._centers.items():
            # 余弦距离
            dot = np.dot(emb, center.center)
            dist = 1.0 - dot  # 两个 L2 归一化向量的余弦距离
            distances.append((dtype, float(dist)))
        distances.sort(key=lambda x: x[1])
        return distances[:top_k]

    def mahalanobis_distance(self, defect_type: str, embedding: np.ndarray) -> Optional[float]:
        """计算到指定 defect_type 中心的马氏距离。"""
        center = self._centers.get(defect_type)
        if center is None or center.sample_count < 2:
            return None
        diff = embedding.astype(np.float32) - center.center
        # 使用对角协方差近似
        var = center.variance + 1e-8
        return float(np.sqrt(np.sum(diff * diff / var)))

    def is_novel(self, embedding: np.ndarray, threshold: float) -> bool:
        """判断 embedding 是否代表新类型缺陷。
        距离所有已知中心都超过 threshold 则视为 novel。
        """
        nearest = self.query_nearest(embedding, top_k=1)
        if not nearest:
            return True
        return nearest[0][1] > threshold

    def get_center(self, defect_type: str) -> Optional[DefectCenter]:
        return self._centers.get(defect_type)

    def list_types(self) -> list[str]:
        return sorted(self._centers.keys())

    def center_count(self) -> int:
        return len(self._centers)

    def save(self, path: str) -> None:
        """保存所有中心到 JSON 文件。"""
        data = {
            "alpha": self.alpha,
            "dim": self._dim,
            "centers": [c.to_dict() for c in self._centers.values()],
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2))

    @classmethod
    def load(cls, path: str) -> "EMAFeatureCenter":
        """从 JSON 文件加载所有中心。"""
        data = json.loads(Path(path).read_text("utf-8"))
        instance = cls(alpha=data["alpha"], dim=data["dim"])
        for cdata in data["centers"]:
            center = DefectCenter(
                defect_type=cdata["defect_type"],
                center=np.array(cdata["center"], dtype=np.float32),
                sample_count=cdata["sample_count"],
                variance=np.array(cdata["variance"], dtype=np.float32),
                last_updated=cdata.get("last_updated", ""),
            )
            instance._centers[center.defect_type] = center
        return instance
```

- [ ] **Step 2: Commit**

```bash
git add seat_defect_core/calibration/feature_center.py
git commit -m "feat(calibration): 实现 EMAFeatureCenter — 缺陷类型特征中心 EMA 追踪"
```

---

### Task 6: 实现 CalibrationRegistry

**Files:**
- Create: `seat_defect_core/calibration/registry.py`

- [ ] **Step 1: 实现 CalibrationRegistry**

```python
"""Unified calibration registry — per-camera indexed access to all calibration components."""

from __future__ import annotations

from typing import Optional

import numpy as np

from .._protocol import UnifiedEmbedding
from .camera_normalizer import CameraNormalizer
from .config import CalibrationConfig
from .feature_center import EMAFeatureCenter
from .projector import EmbeddingProjector
from .whitening import WhiteningTransform


class CalibrationRegistry:
    """按 camera_id 索引所有 calibration 组件。

    一个 camera 的完整校准链路：
        registry.normalize(camera_id, features)
        registry.project(features)
        registry.whiten(unified_emb)

    projector / whitening / ema_center 跨机位共享，
    normalizer 必须 per-camera。
    """

    def __init__(self, config: CalibrationConfig):
        self.config = config
        self._normalizers: dict[str, CameraNormalizer] = {}
        self._projector: Optional[EmbeddingProjector] = None
        self._whitening: Optional[WhiteningTransform] = None
        self._ema_center: Optional[EMAFeatureCenter] = None

        self._load_from_config()

    def _load_from_config(self) -> None:
        cfg = self.config
        if cfg.projection.enabled and cfg.projection.projector_path:
            self._projector = EmbeddingProjector.load(cfg.projection.projector_path)
        if cfg.whitening.enabled and cfg.whitening.matrix_path:
            self._whitening = WhiteningTransform.load(cfg.whitening.matrix_path)
        if cfg.ema_center.enabled and cfg.ema_center.centers_path:
            self._ema_center = EMAFeatureCenter.load(cfg.ema_center.centers_path)
        elif cfg.ema_center.enabled:
            self._ema_center = EMAFeatureCenter(
                alpha=cfg.ema_center.alpha,
                dim=384,
            )

    def register_camera(self, camera_id: str, normalizer: CameraNormalizer) -> None:
        self._normalizers[camera_id] = normalizer

    def load_camera_normalizer(self, camera_id: str, path: str) -> CameraNormalizer:
        normalizer = CameraNormalizer.load(path)
        self._normalizers[camera_id] = normalizer
        return normalizer

    def get_normalizer(self, camera_id: str) -> Optional[CameraNormalizer]:
        return self._normalizers.get(camera_id)

    def normalize(self, camera_id: str, features: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        """机位级标准化。未注册 camera 则返回原值。"""
        normalizer = self._normalizers.get(camera_id)
        if normalizer is None:
            return features
        return normalizer.normalize(features)

    def project(self, features: dict[str, np.ndarray]) -> Optional[np.ndarray]:
        """投影到 384-dim。projector 未加载则返回 None。"""
        if self._projector is None:
            return None
        return self._projector.project(features)

    def whiten(self, embedding: np.ndarray) -> np.ndarray:
        """ZCA 白化。whitening 未加载则返回原值。"""
        if self._whitening is None:
            return embedding
        return self._whiten(embedding)

    def calibrate(
        self, camera_id: str, features: dict[str, np.ndarray]
    ) -> Optional[UnifiedEmbedding]:
        """执行完整校准链路：normalize → project → whiten → UnifiedEmbedding。

        Returns:
            UnifiedEmbedding 如果 projection 可用，否则 None
        """
        if not self.config.enabled:
            return None

        normalized = self.normalize(camera_id, features)
        vec = self.project(normalized)
        if vec is None:
            return None

        if self._whitening is not None:
            vec = self._whiten(vec)

        return UnifiedEmbedding(
            vector=vec.tolist(),
            contract_version="1.0.0",
            source="efficientad_projected",
        )

    def update_ema_center(self, defect_type: str, embedding: np.ndarray) -> None:
        """更新 EMA 中心。"""
        if self._ema_center is not None:
            self._ema_center.update(defect_type, embedding)

    def query_nearest(self, embedding: np.ndarray, top_k: int = 5) -> list[tuple[str, float]]:
        if self._ema_center is not None:
            return self._ema_center.query_nearest(embedding, top_k)
        return []

    def is_novel(self, embedding: np.ndarray) -> bool:
        if self._ema_center is None:
            return False
        return self._ema_center.is_novel(embedding, self.config.ema_center.novelty_threshold)

    @property
    def projector(self) -> Optional[EmbeddingProjector]:
        return self._projector

    @property
    def ema_center(self) -> Optional[EMAFeatureCenter]:
        return self._ema_center
```

- [ ] **Step 2: Commit**

```bash
git add seat_defect_core/calibration/registry.py
git commit -m "feat(calibration): 实现 CalibrationRegistry — 统一校准入口"
```

---

### Task 7: 更新 calibration/__init__.py 导出所有组件

**Files:**
- Modify: `seat_defect_core/calibration/__init__.py`

- [ ] **Step 1: 更新 __init__.py**

```python
"""Feature calibration layer — cross-camera feature normalization, projection, and center tracking."""

from __future__ import annotations

from .camera_normalizer import CameraNormalizer, CameraNormStats
from .config import (
    CalibrationConfig,
    CameraNormConfig,
    EMACenterConfig,
    ProjectionConfig,
    WhiteningConfig,
)
from .feature_center import DefectCenter, EMAFeatureCenter
from .projector import EmbeddingProjector, ProjectionParams
from .registry import CalibrationRegistry
from .whitening import WhiteningTransform

__all__ = [
    "CalibrationConfig",
    "CalibrationRegistry",
    "CameraNormConfig",
    "CameraNormalizer",
    "CameraNormStats",
    "DefectCenter",
    "EMAFeatureCenter",
    "EmbeddingProjector",
    "ProjectionConfig",
    "ProjectionParams",
    "WhiteningConfig",
    "WhiteningTransform",
]
```

- [ ] **Step 2: Commit**

```bash
git add seat_defect_core/calibration/__init__.py
git commit -m "feat(calibration): 更新 __init__.py 导出所有 calibration 组件"
```

---

### Task 8: 扩展 proposal/config.py — 新增 CascadingBudgetConfig

**Files:**
- Modify: `seat_defect_core/proposal/config.py`

- [ ] **Step 1: 在文件末尾追加 CascadingBudgetConfig**

在原文件 `ProposalConfig` 类定义之后追加：

```python
@dataclass
class CascadingBudgetConfig:
    """Configuration for cascading (proposal + filter) budget control."""
    enabled: bool = True

    # Proposal 阶段（复用现有 BudgetConfig）
    proposal: BudgetConfig = field(default_factory=BudgetConfig)

    # Filter 阶段
    filter_budget_ratio: float = 0.4       # Proposal 后最多 40% 时间给 Filter
    filter_hard_limit_ms: float = 8.0      # Filter 阶段硬上限
    filter_cost_ema_alpha: float = 0.95    # per-patch cost 的 EMA 系数
    filter_min_patches: int = 1            # 即使预算不够也最少送几个 patch

    # 紧急熔断
    emergency_filter_ratio: float = 0.1    # 剩余预算低于此比例触发 emergency
```

需要在文件顶部新增 `from dataclasses import field`（如果尚未导入）。

- [ ] **Step 2: 更新 proposal/__init__.py 导出**

```python
from __future__ import annotations

from .config import BudgetConfig, BudgetScope, CascadingBudgetConfig, ProposalConfig
from .generator import ProposalGenerator
from .budget import BudgetController, CascadingBudgetController
from .aggregation import aggregate_proposals

__all__ = [
    "BudgetConfig",
    "BudgetScope",
    "BudgetController",
    "CascadingBudgetConfig",
    "CascadingBudgetController",
    "ProposalConfig",
    "ProposalGenerator",
    "aggregate_proposals",
]
```

- [ ] **Step 3: Commit**

```bash
git add seat_defect_core/proposal/config.py seat_defect_core/proposal/__init__.py
git commit -m "feat(proposal): 新增 CascadingBudgetConfig 两级预算配置"
```

---

### Task 9: 扩展 proposal/budget.py — 实现 CascadingBudgetController

**Files:**
- Modify: `seat_defect_core/proposal/budget.py`

- [ ] **Step 1: 在 BudgetController 类之后追加 CascadingBudgetController**

在文件末尾的 `_estimate_cc_count` 方法之后追加：

```python
@dataclass
class FilterBudgetState:
    """Filter 阶段的预算追踪状态。"""
    estimated_cost_per_patch_ms: float = 3.0  # 初始估计
    recent_costs_ms: list[float] = field(default_factory=list)
    skip_count: int = 0
    emergency_skip_count: int = 0


class CascadingBudgetController:
    """两级预算控制器：Proposal + Filter 级联。

    包装现有的 BudgetController，新增 Filter 阶段的预算感知。
    schedule_filter() 根据剩余预算动态决定哪些 proposal 送 Filter。
    """

    def __init__(self, config: CascadingBudgetConfig | None = None):
        from .config import CascadingBudgetConfig as _CascadingBudgetConfig

        self.config = config or _CascadingBudgetConfig()
        self._proposal = BudgetController(self.config.proposal)
        self._filter_state = FilterBudgetState()

    def start_frame(self) -> None:
        """在新一帧开始时调用，复用 proposal 的计时逻辑。"""
        self._proposal.start_frame()

    def elapsed_ms(self) -> float:
        return self._proposal.elapsed_ms()

    def remaining_budget_ms(self) -> float:
        """Proposal 阶段后的剩余预算。"""
        return self._proposal.remaining_budget_ms()

    def filter_budget_ms(self) -> float:
        """Filter 阶段可用预算上限。"""
        return min(
            self.config.filter_hard_limit_ms,
            self.remaining_budget_ms() * self.config.filter_budget_ratio,
        )

    def regulate(self, heatmap: np.ndarray) -> tuple[float, int, str]:
        """委托给内部 BudgetController。"""
        return self._proposal.regulate(heatmap)

    def record_cc_count(self, count: int) -> None:
        self._proposal.record_cc_count(count)

    def schedule_filter(
        self, proposals: list[Any]
    ) -> tuple[list[Any], list[Any], str]:
        """根据剩余预算决定哪些 proposal 送 Filter。

        Args:
            proposals: 按 priority 已排序的 proposal 列表

        Returns:
            (to_filter, skip, mode)
            to_filter — 送 Filter 推理的 proposal
            skip — 因预算不足跳过的 proposal
            mode — "full" | "partial" | "skip_all" | "emergency"
        """
        if not self.config.enabled:
            return (proposals, [], "full")

        budget_ms = self.filter_budget_ms()
        hard_limit = self.config.filter_hard_limit_ms
        emergency_limit = hard_limit * self.config.emergency_filter_ratio

        # Emergency: 剩余预算极少
        if budget_ms < emergency_limit:
            self._filter_state.emergency_skip_count += 1
            for p in proposals:
                if p.filter_result is None:
                    p.filter_result = self._build_skip_result("emergency")
            return ([], proposals, "emergency")

        # 计算可处理的最大 patch 数
        max_filter = max(1, int(
            budget_ms / max(0.1, self._filter_state.estimated_cost_per_patch_ms)
        ))
        max_filter = max(self.config.filter_min_patches, max_filter)

        if max_filter >= len(proposals):
            return (proposals, [], "full")

        if max_filter >= self.config.filter_min_patches:
            self._filter_state.skip_count += len(proposals) - max_filter
            to_filter = proposals[:max_filter]
            skip = proposals[max_filter:]
            for p in skip:
                if p.filter_result is None:
                    p.filter_result = self._build_skip_result("partial_budget")
            return (to_filter, skip, "partial")

        # 一个都处理不了
        self._filter_state.skip_count += len(proposals)
        for p in proposals:
            if p.filter_result is None:
                p.filter_result = self._build_skip_result("skip_all")
        return ([], proposals, "skip_all")

    def record_filter_cost(self, num_patches: int, total_ms: float) -> None:
        """每帧结束后反馈实际 Filter 耗时，更新 EMA 估计。"""
        if num_patches == 0:
            return
        cost = total_ms / num_patches
        alpha = self.config.filter_cost_ema_alpha
        self._filter_state.estimated_cost_per_patch_ms = (
            alpha * self._filter_state.estimated_cost_per_patch_ms
            + (1.0 - alpha) * cost
        )
        self._filter_state.recent_costs_ms.append(total_ms)
        if len(self._filter_state.recent_costs_ms) > 100:
            self._filter_state.recent_costs_ms.pop(0)

    @staticmethod
    def _build_skip_result(reason: str) -> "FilterResult":
        from .._protocol import FilterResult

        return FilterResult(
            is_real_defect=True,  # 保守：不抑制
            confidence=0.0,
            real_defect_score=0.0,
            false_alarm_score=0.0,
            class_id=1,
            diagnostics={"filter_mode": "budget_skip", "reason": reason},
        )
```

- [ ] **Step 2: Commit**

```bash
git add seat_defect_core/proposal/budget.py
git commit -m "feat(proposal): 实现 CascadingBudgetController 两级预算控制"
```

---

### Task 10: 在 config.py 中为 CameraConfig 添加 calibration 字段

**Files:**
- Modify: `seat_defect_core/config.py`

- [ ] **Step 1: 在 CameraConfig 中添加 calibration 字段**

在 `CameraConfig` 类的 `rule_engine` 字段之后添加：

```python
    calibration: CalibrationConfig | None = None
```

并在文件顶部导入中增加：

```python
from .calibration import CalibrationConfig
```

- [ ] **Step 2: Commit**

```bash
git add seat_defect_core/config.py
git commit -m "feat(config): CameraConfig 新增 calibration 配置字段"
```

---

### Task 11: 在 service/core.py 中集成 CalibrationRegistry

**Files:**
- Modify: `seat_defect_core/service/core.py`

- [ ] **Step 1: 在 InspectionService.__init__ 中初始化 CalibrationRegistry**

修改 `InspectionService.__init__`：

```python
def __init__(self, config: InspectionConfig) -> None:
    self.config = config
    self._pipeline_cache: Dict[str, Dict[str, CameraPipeline]] = {}
    self._model_cache = AnomalyModelCache(self)
    self._anomaly_predictor = EfficientADPredictor()
    self._trackers: Dict[str, Any] = {}
    # 初始化 calibration（使用第一个 camera 的配置，或默认配置）
    self._calibration_registry = self._init_calibration()

def _init_calibration(self) -> Optional[CalibrationRegistry]:
    """从配置中初始化 CalibrationRegistry。"""
    from ..calibration import CalibrationConfig, CalibrationRegistry

    # 从 CameraConfig 中查找 calibration 配置
    for camera in self.config.cameras:
        if camera.calibration is not None:
            return CalibrationRegistry(camera.calibration)
    # 默认：创建空 registry
    return CalibrationRegistry(CalibrationConfig())

@property
def calibration(self) -> Optional[CalibrationRegistry]:
    return self._calibration_registry
```

并在文件顶部导入区添加：

```python
from typing import Optional as _OptionalType
# 在 TYPE_CHECKING 或者直接导入：
from ..calibration import CalibrationRegistry
```

- [ ] **Step 2: Commit**

```bash
git add seat_defect_core/service/core.py
git commit -m "feat(service): InspectionService 集成 CalibrationRegistry"
```

---

### Task 12: 在 service/inspection_camera.py 中接入 calibration + cascading budget

**Files:**
- Modify: `seat_defect_core/service/inspection_camera.py`

- [ ] **Step 1: 替换 Proposal + Filter 逻辑为 calibration + cascading budget 版本**

替换 `inspect_prepared_camera` 中从 `# --- Region Proposal + Dual-Modal Filter ---` 到 `# Override status if filter suppressed the anomaly` 的整段逻辑：

```python
    # --- Region Proposal + Dual-Modal Filter (with Calibration & Cascading Budget) ---
    filter_result: Optional[FilterResult] = None
    proposals: list[Any] = []

    if texture_result.is_anomaly:
        filter_svc = getattr(service, 'filter_service', None)
        if filter_svc is not None:
            try:
                proposal_cfg = getattr(camera, 'proposal', None) or ProposalConfig()
                cascading_cfg = getattr(proposal_cfg, 'cascading_budget', None)
                if cascading_cfg is not None:
                    budget_ctrl = CascadingBudgetController(cascading_cfg)
                else:
                    budget_ctrl = BudgetController(proposal_cfg.budget)
                generator = ProposalGenerator(proposal_cfg, budget_ctrl=budget_ctrl)
                isolation_key = f"{seat_model_id or 'unknown'}|{camera.camera_id}|default"

                roi_h, roi_w = prepared.roi.aligned_roi_image.shape[:2]
                roi_bbox = (
                    int(prepared.roi.crop_box.x1) if prepared.roi.crop_box is not None else 0,
                    int(prepared.roi.crop_box.y1) if prepared.roi.crop_box is not None else 0,
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

                # --- Calibration: normalize + project + whiten ---
                unified_emb: Optional[np.ndarray] = None
                calibration = getattr(service, 'calibration', None)
                if calibration is not None and texture_result.features:
                    calibrated = calibration.calibrate(camera.camera_id, texture_result.features)
                    if calibrated is not None:
                        unified_emb = np.array(calibrated.vector, dtype=np.float32)

                # --- Identity Linking (with unified embedding) ---
                if proposals:
                    tracker = getattr(service, '_trackers', {})
                    cam_tracker = tracker.get(camera.camera_id)
                    if cam_tracker is None and getattr(camera, 'track', None) is not None:
                        from ..tracking import DefectTracker
                        cam_tracker = DefectTracker(camera.camera_id, camera.track)
                        tracker[camera.camera_id] = cam_tracker
                        service._trackers = tracker
                    if cam_tracker is not None:
                        proposals = cam_tracker.update(proposals)

                # --- Cascading Budget: schedule which proposals get Filter ---
                if proposals:
                    if isinstance(budget_ctrl, CascadingBudgetController):
                        to_filter, skip_list, filter_mode = budget_ctrl.schedule_filter(proposals)
                    else:
                        to_filter, skip_list, filter_mode = proposals, [], "full"

                    patch_crops = generator.extract_patch_crops(
                        prepared.roi.aligned_roi_image, to_filter)
                    patch_features_list = []
                    if texture_result.features:
                        patch_features_list = generator.extract_patch_features(
                            texture_result.features, to_filter, (roi_h, roi_w))

                    filter_start_ms = perf_counter()
                    for i, proposal in enumerate(to_filter):
                        patch_img = patch_crops[i] if i < len(patch_crops) else None
                        patch_feats = patch_features_list[i] if i < len(patch_features_list) else None
                        if patch_img is not None:
                            pf_result = filter_svc.predict_dual_modal(
                                patch_img, patch_feats,
                                unified_emb=unified_emb.tolist() if unified_emb is not None else None,
                            )
                            proposal.filter_result = pf_result

                    if isinstance(budget_ctrl, CascadingBudgetController):
                        budget_ctrl.record_filter_cost(
                            len(to_filter),
                            (perf_counter() - filter_start_ms) * 1000.0,
                        )

                    # Aggregate to ROI-level decision
                    filter_result = aggregate_proposals(proposals)

            except Exception:
                import traceback
                traceback.print_exc()
                filter_result = FilterResult(
                    is_real_defect=True, confidence=0.0,
                    real_defect_score=0.0, false_alarm_score=0.0,
                    class_id=1, diagnostics={"mode": "error_fallback"},
                )
```

需要在文件顶部导入区增加：

```python
import numpy as np
from ..proposal import CascadingBudgetController
```

- [ ] **Step 2: Commit**

```bash
git add seat_defect_core/service/inspection_camera.py
git commit -m "feat(pipeline): 接入 Calibration + Cascading Budget 到检测流程"
```

---

### Task 13: 编写单元测试

**Files:**
- Create: `seat_defect_core/tests/__init__.py`
- Create: `seat_defect_core/tests/test_calibration.py`

- [ ] **Step 1: 创建 tests/__init__.py**

```python
"""Tests for seat_defect_core."""
```

- [ ] **Step 2: 编写 test_calibration.py**

```python
"""Tests for calibration layer components."""

from __future__ import annotations

import numpy as np
import pytest

from seat_defect_core.calibration import (
    CalibrationConfig,
    CalibrationRegistry,
    CameraNormalizer,
    CameraNormConfig,
    EMAFeatureCenter,
    EmbeddingProjector,
    ProjectionConfig,
    WhiteningConfig,
    WhiteningTransform,
)


class TestCameraNormalizer:
    def test_fit_and_normalize(self):
        normalizer = CameraNormalizer()
        # 生成模拟的正常特征：每个 key 是 (8, 8, 64) 的特征图
        features_list = []
        for _ in range(20):
            features_list.append({
                "teacher_l1": np.random.randn(8, 8, 64).astype(np.float32),
                "teacher_l2": np.random.randn(4, 4, 128).astype(np.float32),
                "teacher_l3": np.random.randn(2, 2, 256).astype(np.float32),
                "difference": np.random.randn(16, 16, 64).astype(np.float32),
            })

        normalizer.fit(features_list)
        assert normalizer.is_fitted

        # 验证标准化后每个 key 的 per-channel mean ≈ 0, std ≈ 1
        normalized = normalizer.normalize(features_list[0])
        for key in ["teacher_l1", "teacher_l2", "teacher_l3", "difference"]:
            val = normalized[key]
            flat = val.reshape(-1, val.shape[-1])
            channel_mean = flat.mean(axis=0)
            channel_std = flat.std(axis=0)
            assert np.allclose(channel_mean, 0.0, atol=0.3)
            assert np.allclose(channel_std, 1.0, atol=0.3)

    def test_save_and_load(self, tmp_path):
        normalizer = CameraNormalizer()
        features_list = [{
            "teacher_l1": np.random.randn(8, 8, 64).astype(np.float32),
        }]
        normalizer.fit(features_list)

        path = str(tmp_path / "norm_stats.npz")
        normalizer.save(path)
        loaded = CameraNormalizer.load(path)
        assert loaded.is_fitted

        # 验证加载后结果一致
        original = normalizer.normalize(features_list[0])
        reloaded = loaded.normalize(features_list[0])
        for key in original:
            assert np.allclose(original[key], reloaded[key], atol=1e-6)

    def test_online_update(self):
        normalizer = CameraNormalizer()
        feats = {
            "teacher_l1": np.ones((8, 8, 64), dtype=np.float32) * 5.0,
        }
        normalizer.update(feats)
        assert normalizer.is_fitted
        stats = normalizer._stats["teacher_l1"]
        assert np.allclose(stats.mean, 5.0, atol=0.01)

    def test_missing_key_passthrough(self):
        normalizer = CameraNormalizer()
        features_list = [{
            "teacher_l1": np.random.randn(4, 4, 32).astype(np.float32),
        }]
        normalizer.fit(features_list)

        # teacher_l2 没有 fit，应该原值通过
        result = normalizer.normalize({
            "teacher_l1": np.random.randn(4, 4, 32).astype(np.float32),
            "teacher_l2": np.random.randn(2, 2, 64).astype(np.float32),
        })
        assert "teacher_l2" in result


class TestEmbeddingProjector:
    def test_fit_and_project(self):
        features_list = []
        for _ in range(30):
            features_list.append({
                "teacher_l1": np.random.randn(8, 8, 64).astype(np.float32),
                "teacher_l2": np.random.randn(4, 4, 128).astype(np.float32),
            })

        projector = EmbeddingProjector.fit(
            features_list,
            output_dim=64,
            pool_sizes={"teacher_l1": (1, 1), "teacher_l2": (1, 1)},
        )
        assert projector.is_fitted
        assert projector.output_dim == 64

        vec = projector.project(features_list[0])
        assert vec.shape == (64,)
        # 应该 L2 归一化
        assert abs(np.linalg.norm(vec) - 1.0) < 0.01

    def test_missing_feature_raises(self):
        projector = EmbeddingProjector.fit(
            [{"teacher_l1": np.random.randn(8, 8, 64).astype(np.float32)}],
            output_dim=32,
        )
        with pytest.raises(KeyError):
            projector.project({"wrong_key": np.random.randn(8, 8, 64).astype(np.float32)})

    def test_save_and_load(self, tmp_path):
        features_list = [{
            "teacher_l1": np.random.randn(8, 8, 64).astype(np.float32),
        }]
        projector = EmbeddingProjector.fit(features_list, output_dim=32)

        path = str(tmp_path / "projector.npz")
        projector.save(path)
        loaded = EmbeddingProjector.load(path)

        v1 = projector.project(features_list[0])
        v2 = loaded.project(features_list[0])
        assert np.allclose(v1, v2, atol=1e-6)


class TestWhiteningTransform:
    def test_fit_and_whiten(self):
        # 生成有相关性的 embedding
        rng = np.random.RandomState(42)
        base = rng.randn(100, 64).astype(np.float32)
        # 添加人工相关性
        M = rng.randn(64, 64).astype(np.float32) * 0.3 + np.eye(64)
        correlated = base @ M.T
        # L2 normalize
        correlated = correlated / np.linalg.norm(correlated, axis=1, keepdims=True)

        whitening = WhiteningTransform(dim=64)
        whitening.fit([correlated[i] for i in range(100)])

        whitened = whitening.whiten(correlated[0])
        assert whitened.shape == (64,)
        assert abs(np.linalg.norm(whitened) - 1.0) < 0.01

    def test_not_fitted_raises(self):
        whitening = WhiteningTransform(dim=64)
        with pytest.raises(RuntimeError):
            whitening.whiten(np.random.randn(64).astype(np.float32))

    def test_save_and_load(self, tmp_path):
        rng = np.random.RandomState(42)
        embeddings = rng.randn(50, 32).astype(np.float32)
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)

        whitening = WhiteningTransform(dim=32)
        whitening.fit([embeddings[i] for i in range(50)])

        path = str(tmp_path / "whitening.npz")
        whitening.save(path)
        loaded = WhiteningTransform.load(path)

        w1 = whitening.whiten(embeddings[0])
        w2 = loaded.whiten(embeddings[0])
        assert np.allclose(w1, w2, atol=1e-6)


class TestEMAFeatureCenter:
    def test_update_and_query(self):
        ema = EMAFeatureCenter(alpha=0.9, dim=32)
        emb1 = np.ones(32, dtype=np.float32) / np.sqrt(32)  # L2 normalized
        emb2 = np.full(32, -0.5, dtype=np.float32)
        emb2 = emb2 / np.linalg.norm(emb2)

        ema.update("defect_A", emb1)
        ema.update("defect_B", emb2)

        # 查询 nearest
        nearest = ema.query_nearest(emb1, top_k=2)
        assert nearest[0][0] == "defect_A"
        assert nearest[0][1] < nearest[1][1]  # 第一个更近

    def test_is_novel(self):
        ema = EMAFeatureCenter(alpha=0.9, dim=32)
        emb = np.ones(32, dtype=np.float32) / np.sqrt(32)
        ema.update("defect_A", emb)

        # 相似的 embedding 不是 novel
        similar = emb + np.random.randn(32).astype(np.float32) * 0.01
        similar = similar / np.linalg.norm(similar)
        assert not ema.is_novel(similar, threshold=0.3)

        # 很远的 embedding 是 novel
        novel = -emb
        assert ema.is_novel(novel, threshold=0.3)

    def test_save_and_load(self, tmp_path):
        ema = EMAFeatureCenter(alpha=0.9, dim=32)
        emb = np.ones(32, dtype=np.float32) / np.sqrt(32)
        ema.update("defect_A", emb)

        path = str(tmp_path / "centers.json")
        ema.save(path)
        loaded = EMAFeatureCenter.load(path)

        assert loaded.center_count() == 1
        assert loaded.list_types() == ["defect_A"]
        center = loaded.get_center("defect_A")
        assert np.allclose(center.center, emb, atol=1e-5)


class TestCalibrationRegistry:
    def test_calibrate_full_pipeline(self, tmp_path):
        # 1. 创建并保存 normalizer
        normalizer = CameraNormalizer()
        normalizer.fit([{
            "teacher_l1": np.random.randn(8, 8, 64).astype(np.float32),
            "teacher_l2": np.random.randn(4, 4, 128).astype(np.float32),
        }])
        norm_path = str(tmp_path / "norm.npz")
        normalizer.save(norm_path)

        # 2. 创建并保存 projector
        projector = EmbeddingProjector.fit(
            [{"teacher_l1": np.random.randn(8, 8, 64).astype(np.float32),
              "teacher_l2": np.random.randn(4, 4, 128).astype(np.float32)}],
            output_dim=32,
        )
        proj_path = str(tmp_path / "proj.npz")
        projector.save(proj_path)

        # 3. 创建 registry
        config = CalibrationConfig(
            projection=ProjectionConfig(enabled=True, projector_path=proj_path),
            whitening=WhiteningConfig(enabled=False),  # 测试不开启白化
        )
        registry = CalibrationRegistry(config)
        registry.register_camera("cam_front", normalizer)

        # 4. 执行完整校准
        feats = {
            "teacher_l1": np.random.randn(8, 8, 64).astype(np.float32),
            "teacher_l2": np.random.randn(4, 4, 128).astype(np.float32),
        }
        result = registry.calibrate("cam_front", feats)
        assert result is not None
        assert len(result.vector) == 32
        assert result.contract_version == "1.0.0"
        assert result.source == "efficientad_projected"

    def test_calibrate_disabled(self):
        config = CalibrationConfig(enabled=False)
        registry = CalibrationRegistry(config)
        assert registry.calibrate("any", {}) is None
```

- [ ] **Step 3: 运行测试**

```bash
cd /Users/yyh/code/offline-analysis-platform && uv run pytest seat_defect_core/tests/test_calibration.py -v
```

Expected: 13 tests PASS

- [ ] **Step 4: Commit**

```bash
git add seat_defect_core/tests/
git commit -m "test(calibration): 添加 calibration 模块单元测试 13 个用例"
```
