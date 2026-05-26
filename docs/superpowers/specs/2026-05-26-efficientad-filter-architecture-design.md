# EfficientAD → Filter 架构升级设计

**日期**: 2026-05-26
**状态**: 设计完成，待实现

## 动机

当前在线检测系统中，EfficientAD 只输出 `anomaly_score`（标量），中间层特征被丢弃。Filter Classifier 虽然代码存在（`classifier/engine.py`），但未接入 `inspection_camera.py` 推理 pipeline。两个核心问题：

1. **Filter 缺少 anomaly representation**：Filter 应该学习异常"长什么样"，而非只知道"有多异常"。anomaly embedding >> anomaly score。
2. **Filter 缺少空间定位**：全 ROI 直接送 Filter 会稀释缺陷信号。应该 anomaly heatmap → connected components → region crop → per-patch Filter。

## 核心设计

### 1. 数据协议层 (`defect_protocol/`)

新建独立 Python 包，零依赖（仅 python>=3.11），定义在线推理与离线训练的共享数据契约。

```
defect_protocol/
├── __init__.py
├── pyproject.toml
├── entities.py          # PatchProposal, EfficientADFeatures, BoundingBox
├── serialization.py     # to_dict() / from_dict() / to_json()
├── types.py             # ProposalId, FeatureRef, ImageRef
└── README.md
```

**核心数据结构 `PatchProposal`**：

| 字段 | 类型 | 说明 |
|---|---|---|
| `proposal_id` | str (UUID) | 全链路唯一标识 |
| `isolation_key` | IsolationKey | seat_model + camera + region |
| `source_roi` | ROIContext | 父 ROI 的 bbox + image_ref |
| `patch_image` | ImageRef | 缺陷 patch 裁剪图 (MinIO key + bbox) |
| `patch_bbox` | BoundingBox | patch 在 ROI 坐标系中的位置 |
| `anomaly_context` | AnomalyContext | score + heatmap_ref + feature_ref |
| `efficientad_features` | EfficientADFeatures | teacher_l1/2/3 + difference |
| `proposal_metadata` | ProposalMetadata | component_area + rank + generation_params |
| `filter_result` | FilterResult \| None | 在线填充，离线可回填 |

大 Tensor 通过 MinIO `.npy` 存储，协议层只存引用 key。

### 2. EfficientAD Feature Harvesting

在 `EfficientADService.predict()` 中注册 PyTorch forward hook：

| Layer | Source | Shape | 语义 |
|---|---|---|---|
| `teacher_l1` | Teacher block1 | 56×56×C | 底层纹理 |
| `teacher_l2` | Teacher block2 | 28×28×C | 中层结构 |
| `teacher_l3` | Teacher block3 | 14×14×C | 高层语义 |
| `difference` | \|Student - Teacher\| | 224×224×C | 异常偏差 |

特征按 proposal 存入 MinIO：`features/{seat_model}/{camera}/{date}/{proposal_id}/teacher_l1.npy` 等。

### 3. Region Proposal Refinement

两阶段彻底分离：

**Stage 1 - Proposal Generation（优化 Recall）**:
```
Heatmap → adaptive threshold (mean+1.5*std) → morphological cleanup
→ connected components → filter (area≥16px², solidity≥0.3)
→ bbox expansion (+10% padding) → patch crops + feature extraction
```

**Stage 2 - Proposal Aggregation（优化 Precision）**:
```
Per-patch Filter inference → weighted aggregation:
  weight_i = normalize(area_i^0.5 × anomaly_score_i)
  weighted_confidence = Σ(weight_i × confidence_i) / Σ(weight_i)
  is_real_defect = weighted_confidence ≥ confidence_threshold
```

新模块 `seat_defect_core/proposal/`：
- `generator.py`: ProposalGenerator
- `aggregation.py`: aggregate_proposals()
- `config.py`: ProposalConfig

### 4. Dual-Modal Filter

**架构**：
```
Image Branch:                    Feature Branch:
Patch 448×448×3                  teacher_l1 + l2 + l3 + difference
    ↓                                ↓
MobileNetV3-Small               Per-layer RoIAlign → FC(64)
    ↓                                ↓
GAP → FC(256) → L2 Norm         Concat → FC(256) → L2 Norm
    ↓                                ↓
    └──────── Concat [f_img | f_ead] (R⁵¹²) ────────┘
                    ↓
              FC(128) → ReLU → Dropout(0.3)
                    ↓
              FC(64) → ReLU
                    ↓
              FC(1) → Sigmoid → P(real_defect)
```

**关键设计**：
- Image branch: MobileNetV3-Small, input **448×448**
- Feature branch dropout: 训练时 20% 概率 zero-out → 纯图像 fallback 能力
- Late fusion via concat
- Focal Loss (γ=2, α=0.75) 处理类别不平衡

**训练参数**：
- Adam, image branch lr=1e-5, feature branch lr=1e-4
- batch_size=32, epochs=50, EarlyStopping patience=10
- Augmentation: RandomFlip + ColorJitter + Rotate±15°
- ReduceLROnPlateau

### 5. 在线推理 Pipeline 集成

改造 `inspection_camera.py:inspect_prepared_camera()`：

```
YOLO → ROI → EfficientAD(+features) → Region Proposal → Dual-Modal Filter → Aggregate → Rules → Fusion
```

- 延迟预算: ~5-10ms extra (N≤5 proposals, GPU batch inference)
- Fallback: Filter 不可用 → score 判定 / features 缺失 → 纯图像 / proposal 失败 → 全 ROI
- 故障安全: Filter 任何失败 → is_real_defect=True

### 6. 离线训练 Pipeline

替换现有 `FilterClassifierTrainer` 为 `DualModalTrainer`。

**训练数据流**：
```
Reviewed clusters → expand to PatchProposals → label propagation
→ load patch_image + EfficientAD features → DualModalDataset
→ train/val split (stratified by cluster)
```

**新模块** `ml/classifier/dual_modal/`：model.py + dataset.py + trainer.py + config.py

**Feature Dropout = 天然兼容**：训练时 20% drop feature branch，模型同时学会有/无 EfficientAD 特征两种推理模式。在线侧 features 缺失时自动退化，无需两套模型。

### 7. 统一数据流

在线→离线：POST /api/anomaly/upload-with-files，JSON 元数据含 proposals 数组 + multipart 文件（patch images + .npy features）

离线→在线：TorchScript 模型通过现有部署流程 → 目标目录 → reload.signal → FilterClassifierService 热重载

## 文件改动清单

### 新增 (5 模块)
- `defect_protocol/` (entities.py, serialization.py, types.py)
- `seat_defect_core/proposal/` (generator.py, aggregation.py, config.py)
- `ml/classifier/dual_modal/` (model.py, dataset.py, trainer.py, config.py)

### 修改 (12 文件)
- `seat_defect_core/config.py` — 新增 ProposalConfig
- `seat_defect_core/core_types/results.py` — TextureAnomalyResult 新增 features, CameraInspectionResult 新增 proposals
- `seat_defect_core/efficientad/engine.py` — forward hook 注册, predict() 返回 features
- `seat_defect_core/classifier/engine.py` — 新增 predict_dual_modal()
- `seat_defect_core/service/inspection_camera.py` — 接入 Proposal + Filter + Aggregation
- `seat_defect_core/anomaly_uploader.py` — 上传 proposals + features, 复用 proposal/generator
- `seat_defect_core/serialization.py` — 序列化 proposals
- `backend/app/schemas/anomaly.py` — 请求 schema 支持 proposals
- `backend/app/services/anomaly/service.py` — 存储 proposals + features
- `backend/workers/training_worker/tasks.py` — train_filter_classifier() → DualModalTrainer
- `backend/services/gate/service.py` — 评估指标升级为 proposal 级

### 删除
- `ml/classifier/trainer.py` — 被 DualModalTrainer 替换

## 设计原则

1. **统一协议** — `defect_protocol/entities.py` 是唯一数据契约，在线和离线通过 PatchProposal 通信
2. **一条管线** — 一个模型、一个训练流程、一个 API 端点。Feature dropout 保证 fallback
3. **故障安全** — Filter 不可用退化为 score 判定，始终坚持 is_real_defect=True on failure
