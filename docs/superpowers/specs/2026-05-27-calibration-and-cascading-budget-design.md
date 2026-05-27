# Feature Calibration Layer + Cascading Budget Manager 设计

## 背景

`seat_defect_core` 已从单模型演进为多模型推理引擎（YOLO → EfficientAD → FilterClassifier），
每个 CameraConfig 可挂独立模型文件，RegionConfig 还可挂区域级 EfficientAD 模型。
复杂度快速膨胀，需要做强模块化和跨机位特征校准。

## 1. 模块架构

新增 `calibration/` 目录，与 `proposal/`、`tracking/` 平级：

```
seat_defect_core/
  calibration/                    # 新增：特征校准层
    __init__.py
    config.py                     # CalibrationConfig
    camera_normalizer.py          # CameraNormalizer — 机位级 mean/std 标准化
    projector.py                  # EmbeddingProjector — EfficientAD features → unified 384-dim
    whitening.py                  # WhiteningTransform — ZCA 白化矩阵
    feature_center.py             # EMAFeatureCenter — 维护每个 defect_type 的特征中心
    registry.py                   # CalibrationRegistry — 按 camera_id 索引所有组件
  proposal/
    config.py                     # 扩展：CascadingBudgetConfig
    budget.py                     # 扩展：CascadingBudgetController
```

### 数据流

```
EfficientAD features (teacher_l1/l2/l3 + difference)
  │
  ├─→ CameraNormalizer.normalize()        # 机位级 per-channel 标准化
  ├─→ EmbeddingProjector.project()        # 投影到 384-dim L2 归一化向量
  └─→ WhiteningTransform.whiten()         # ZCA 白化，去相关 + 等方差
       │
       └─→ UnifiedEmbedding               # 满足 EmbeddingSpaceContract
            │
            ├─→ FilterClassifier.predict()
            ├─→ EMAFeatureCenter.update()
            └─→ DefectTracker.update()
```

## 2. Feature Calibration Layer

### 2.1 CalibrationConfig

```python
@dataclass
class CalibrationConfig:
    enabled: bool = True

    # EMA feature center
    ema_alpha: float = 0.99
    min_samples_for_center: int = 10

    # Camera normalization
    camera_normalization_enabled: bool = True
    norm_stats_path: str = ""

    # Projection
    projection_enabled: bool = True
    projector_path: str = ""

    # Whitening
    whitening_enabled: bool = True
    whitening_method: str = "zca"  # "zca" | "pca"
    whitening_regularization: float = 1e-4
    whitening_matrix_path: str = ""
```

### 2.2 CameraNormalizer

Per-camera, per-channel `(x - mean) / std` 标准化。

- 4 组独立 stats：`teacher_l1`, `teacher_l2`, `teacher_l3`, `difference`
- 离线在正常样本上拟合（`is_anomaly=False`），推理时查表
- 支持 Welford 在线增量更新

### 2.3 EmbeddingProjector

EfficientAD 多尺度特征图 → 384-dim unified embedding。

流程：各尺度 spatial feature → adaptive average pool → concat → Linear(concat_dim, 384) → L2 normalize

投影矩阵离线训练（PCA 初始化 + linear probe finetune），存为 `.npy` 文件。

### 2.4 WhiteningTransform

ZCA 白化矩阵 `W = U @ diag(1/sqrt(S + eps)) @ U^T`。

- 在统一嵌入空间中消除机位间协方差差异
- 与 CameraNormalizer 互补：前者处理 channel-level，后者处理 embedding 维度相关性
- 白化后的 embedding 天然满足 `EmbeddingSpaceContract`（L2 norm + decorrelated）

### 2.5 EMAFeatureCenter

维护跨机位 defect_type 的特征中心 EMA。

- 更新规则：`center = alpha * center + (1-alpha) * new_embedding`
- 方差追踪：`variance = alpha * variance + (1-alpha) * (new - center)^2`
- 查询接口：`query_nearest(embedding, top_k)` → 最近 defect_type
- 新颖性检测：`is_novel(embedding, threshold)` → 是否是新类型缺陷

### 2.6 CalibrationRegistry

统一入口，按 camera_id 索引所有校准组件。

- normalizer per-camera（不同机位特征分布不同）
- projector / whitening / ema_center 跨机位共享（校准后已是统一空间）

## 3. Cascading Budget Manager

### 3.1 两级预算模型

```
帧预算 X ms（默认 15ms）
  ├─ Proposal Budget:  控制 heatmap threshold + K 上限
  └─ Filter Budget:    控制送 Filter 的 proposal 数量
```

### 3.2 CascadingBudgetConfig

```python
@dataclass
class CascadingBudgetConfig:
    enabled: bool = True
    proposal: BudgetConfig                          # 复用现有
    filter_budget_ratio: float = 0.4                # Proposal 后最多 40% 预算留给 Filter
    filter_hard_limit_ms: float = 8.0               # Filter 最大耗时
    filter_cost_ema_alpha: float = 0.95             # per-patch cost EMA 系数
    filter_min_patches: int = 1
    emergency_filter_ratio: float = 0.1
```

### 3.3 CascadingBudgetController

包装现有的 `BudgetController`，新增 `schedule_filter()`：

- **emergency**：剩余预算 < hard_limit * 0.1 → 全部 skip，保守保留 NG
- **full**：预算充足 → 全部送 Filter
- **partial**：预算有限 → 按 anomaly_score * area 降序，前 N 个送 Filter
- **skip_all**：预算耗尽 → 全部 skip，降级为纯 Proposal 判定

per-patch Filter 耗时通过 EMA 估计：`cost = alpha * cost + (1-alpha) * actual_cost`

### 3.4 与现有 BudgetController 的关系

不删除，包装为内部组件：

```
CascadingBudgetController
  ├─ BudgetController (proposal，不变)
  └─ FilterBudgetState  (filter，新增)
```

## 4. Pipeline 接入点

在 `inspection_camera.py:inspect_prepared_camera()` 中：

```
texture_result.is_anomaly:
  1. ProposalGenerator.generate()           # BudgetController 控制 threshold + K
  2. CalibrationRegistry.calibrate()        # features → unified embedding
  3. DefectTracker.update()                 # 身份追踪（用 unified embedding）
  4. CascadingBudgetController.schedule_filter()  # 决定哪些送 Filter
  5. FilterClassifier.predict_dual_modal()  # 只对预算内的 proposal 推理
  6. aggregate_proposals()                  # 聚合为 ROI 级判定
```

## 5. 实施顺序

1. **`calibration/config.py`** + **`calibration/__init__.py`** — 接口定义
2. **`calibration/camera_normalizer.py`** — 最小可用单元，离线拟合 + 推理查表
3. **`calibration/projector.py`** — 特征投影
4. **`calibration/whitening.py`** — ZCA 白化
5. **`calibration/feature_center.py`** — EMA 中心
6. **`calibration/registry.py`** — 统一注册入口
7. **`proposal/budget.py` 扩展** — CascadingBudgetController
8. **`proposal/config.py` 扩展** — CascadingBudgetConfig
9. **`service/inspection_camera.py` 集成** — 接入 pipeline
10. **`config.py` 更新** — CameraConfig 增加 `calibration: CalibrationConfig`
