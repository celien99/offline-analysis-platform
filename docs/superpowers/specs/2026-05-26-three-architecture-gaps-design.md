# Three Architecture Gaps: Budget Controller + Identity Linking + Embedding Space Contract

**日期**: 2026-05-26
**状态**: 设计完成，待实现
**前置**: EfficientAD → Filter Architecture Upgrade (2026-05-26)

## 动机

基于上一轮架构升级，发现三个工程薄弱点：

1. **Proposal 数量不可控**：噪声纹理（织物纹路）可产生 100+ CCs，计算开销在截断前已全部发生，最坏情况延迟不可预测
2. **无 Defect Identity**：每帧 proposal 独立，同一缺陷跨帧/跨相机产生 N 个 anomaly_record，污染聚类和训练数据
3. **Embedding 空间分裂**：在线用 EfficientAD 特征（多尺度 spatial），离线用 DINOv2（384d），两个空间完全独立，聚类发现无法指导在线判定

## 核心设计原则

- **协议层定义契约，实现层执行契约** — 数据结构、embedding space、budget scope 在 `defect_protocol/` 中定义为 protocol，具体实现在各自模块中
- **Canonical Schema 防漂移** — 所有数据结构有 `schema_version`、归一化坐标、`__post_init__` 验证
- **冲突策略显式化** — Identity Linking 的所有冲突场景有明确解决策略

---

## 改进 1: Proposal Budget Controller

### BudgetScope — 作用域定义

Budget 不是无差别控制，而是有明确作用域：

| Scope Level | 控制范围 | 控制手段 | 退出行为 |
|---|---|---|---|
| **PROPOSAL** | 仅 proposal 生成 (threshold + K) | adaptive_threshold + K_limit | 剩余 proposal 丢弃 |
| **PROPOSAL_AND_FILTER** (推荐默认) | proposal + Filter 推理 | 以上 + filter_early_exit | 未推理 proposal → is_real_defect=True (安全) |
| **FULL_PIPELINE** | 全链路 (含 aggregation + rules) | 以上 + aggregation_skip | 跳过聚合 → 直接 anomaly_score 判定 |

### 三态策略

| 模式 | 触发条件 | 行为 |
|---|---|---|
| **Normal** | elapsed < target_latency_ms (15ms) | 完整 pipeline，K 由剩余预算动态决定 |
| **Emergency** | elapsed ≥ hard_limit_ms (20ms) **或** CC count ≥ max_cc_before_emergency (50) | Early exit，跳过 Filter，未处理 proposal 标记 is_real_defect=True |
| **Optimization** | 最近 window_size 帧平均 proposal 数 > 目标 | 持久化提高 adaptive_threshold_multiplier（1.5→2.0→2.5），recovery_rate 缓慢恢复 |

### 自适应阈值

```
base = mean(heatmap) + multiplier × std(heatmap)
budget_factor = min(1.0, remaining_budget_ms / target_latency_ms)
threshold = base + (1 - budget_factor) × std(heatmap)
```

budget 越紧张 → threshold 越高 → proposal 越少。

### BudgetConfig

```python
@dataclass
class BudgetConfig:
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

### 文件改动
- 新增: `seat_defect_core/proposal/budget.py` (BudgetController + BudgetScope 枚举)
- 修改: `proposal/config.py` (BudgetConfig), `proposal/generator.py` (集成 regulate())

---

## 改进 2: Defect Identity Linking

### CanonicalPatchProposal — 防漂移 Schema

Identity Linking 操作的核心数据结构，定义在协议层：

```python
# defect_protocol/canonical_proposal.py
@dataclass
class CanonicalPatchProposal:
    # 不变标识
    proposal_id: str
    schema_version: str = "1.0.0"
    isolation_key: str

    # 空间参照（归一化坐标系 0-1，防漂移）
    roi_bbox_norm: tuple[float, float, float, float]
    patch_bbox_norm: tuple[float, float, float, float]
    roi_size_px: tuple[int, int]  # 实际像素尺寸（反归一化用）

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

    # 生成参数快照
    generation_params: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        assert 0 <= self.patch_bbox_norm[0] < self.patch_bbox_norm[2] <= 1
        assert 0 <= self.patch_bbox_norm[1] < self.patch_bbox_norm[3] <= 1
        assert self.component_area_px > 0
```

### 六态生命周期

```
BIRTH → ACTIVE → TENTATIVE → MATURE → LOST → DEAD
```

- **BIRTH**: 新 proposal 未匹配任何现有 identity
- **ACTIVE**: 首次匹配成功
- **TENTATIVE**: hit_streak ≥ 2，确认为有效 identity
- **MATURE**: hit_streak ≥ 5，触发 upload
- **LOST**: 连续 N 帧未匹配，进入 grace 倒计时
- **DEAD**: grace 归零，从 tracker 移除

### 级联匹配策略

| 阶段 | 匹配方式 | 适用 | 阈值 |
|---|---|---|---|
| Stage 1 | IoU + Kalman 马氏距离 | 同相机连续帧 | IoU≥0.3 且 Mahalanobis≤9.5 |
| Stage 2 | unified_emb 余弦相似度 | 同相机重识别 + 跨相机关联 | cosine≥0.85 |
| Stage 3 | 几何约束验证 | 跨相机后验证 | epipolar distance≤50px |

### 冲突解决策略

| 冲突类型 | 场景 | 解决策略 |
|---|---|---|
| **1:N** (Proposal→Identities) | 一个 proposal 匹配多个 identity | **Best Match Wins**: score = 0.5×IoU + 0.5×cosine_sim，选最高分，超过第二名 ≥0.15 margin，否则标记 ambiguous → 创建新 identity |
| **N:1** (Proposals→Identity) | 多个 proposal 匹配同一 identity | **NMS Merge**: IoU≥0.5 → 合并 bbox (union)，score 取 max；IoU<0.5 → 仅保留最高分 proposal |
| **N:M** (Cross-Camera) | 跨相机 identity 合并冲突 | **Feature Tiebreaker**: cosine_sim > 0.9 → 合并为一个 identity，保持先创建者的 identity_id，后创建者标记为 merged_into |
| **Race Condition** | 同一帧对称匹配 | **Hungarian Algorithm**: 构建 cost matrix (1 - match_score)，全局最优分配 |

### 去重策略

- MATURE (≥5帧) → 选择 best frame (max anomaly_score) 作为代表上传
- 同一 identity 后续帧有更好视角 → PATCH 更新已有 anomaly_record
- 跨相机 identity 合并 → 同一 identity_id，fusion 只计一次

### Kalman 运动模型

6-DOF: (x, y, w, h, vx, vy)，匀速模型，标准 Kalman predict/update。

### 文件改动
- 新增: `seat_defect_core/tracking/` (identity.py, tracker.py, matcher.py, kalman_filter.py, config.py)
- 新增: `defect_protocol/canonical_proposal.py`
- 修改: `inspection_camera.py`, `anomaly_uploader.py`, `core_types/results.py`, `fusion.py`

---

## 改进 3: Embedding Space Contract（协议层契约，非模块）

### 定位

`EmbeddingSpaceContract` 是**协议层契约**——所有模块共享的 representation standard。它不是服务，不是模块，而是"法律"。

```
📐 Contract Layer:  defect_protocol/embedding_space.py
   · dim: 384, norm: L2, similarity: cosine, target_geometry: DINOv2
   · 所有模块必须遵守，不关心谁实现它

🔧 Implementation Layer:  ml/alignment/projector.py
   · AlignmentProjector: EAD features → 384d L2
   · 一种具体实现，可替换
```

### EmbeddingSpaceContract

```python
# defect_protocol/embedding_space.py
@dataclass
class EmbeddingSpaceContract:
    """Representation standard — all modules reference this, not implementations."""
    dim: int = 384
    norm: str = "l2"
    similarity: str = "cosine"
    target_geometry: str = "dinov2_vits14"
    schema_version: str = "1.0.0"

@dataclass
class UnifiedEmbedding:
    """A concrete vector satisfying the contract."""
    vector: list[float]     # 384-dim, L2 normalized
    contract_version: str   # "1.0.0"
    source: str             # "efficientad_projected" | "dinov2"
```

### Alignment Projector（Contract 的实现）

```
EfficientAD Teacher Features (l1/l2/l3/diff)
    → Per-Layer GAP + FC(128) → Concat (512d)
    → Transformer Encoder (2 layers, 4 heads, FFN 1024)
    → FC(384) → L2 Norm
    → satisfies EmbeddingSpaceContract
```

### 训练

- **Loss**: InfoNCE (Contrastive), τ=0.07
- **正样本**: (EAD_proj, DINOv2) 同一 anomaly
- **负样本**: batch 内其他 anomaly 的 DINOv2
- **数据**: 从已审核异常收集成对 (EAD features, DINOv2 embedding)
- **优化器**: AdamW, lr=1e-4, cosine schedule
- **导出**: TorchScript，在线推理加载

### 所有模块通过 Contract 通信

| 消费者 | 用法 | 说明 |
|---|---|---|
| 离线聚类 | DINOv2 → UMAP → HDBSCAN | DINOv2 天然满足 Contract (target geometry) |
| Dual-Modal Filter | unified_emb 作为额外输入 | image + EAD raw + unified_emb 三路融合 |
| DefectTracker | 跨帧/跨相机特征匹配 | 使用 Contract.similarity (cosine) 做 identity 关联 |
| 异常检索 | pgvector 相似度查询 | 在线 proposal 直接检索离线知识库 |
| AlignmentProjector | EAD → 384d L2 | 实现 Contract，将 EAD 特征投影到目标空间 |

### 文件改动
- 新增: `defect_protocol/embedding_space.py` (EmbeddingSpaceContract)
- 新增: `ml/alignment/` (projector.py, trainer.py, dataset.py, config.py) — Contract 的一种实现
- 修改: `classifier/engine.py`, `dual_modal/model.py` (三路融合), `tracking/matcher.py` (使用 Contract.similarity)

---

## 完整文件改动清单

### 新增 (12)
- `defect_protocol/canonical_proposal.py` — CanonicalPatchProposal 规范 schema
- `defect_protocol/embedding_space.py` — EmbeddingSpaceContract 协议
- `seat_defect_core/proposal/budget.py` — BudgetController + BudgetScope
- `seat_defect_core/tracking/` (identity.py, tracker.py, matcher.py, kalman_filter.py, config.py)
- `ml/alignment/` (projector.py, trainer.py, dataset.py, config.py)

### 修改 (11)
- `seat_defect_core/proposal/config.py` — 新增 BudgetConfig (含 BudgetScope)
- `seat_defect_core/proposal/generator.py` — 集成 BudgetController
- `seat_defect_core/service/inspection_camera.py` — 接入 Identity Linking
- `seat_defect_core/anomaly_uploader.py` — MATURE identity → upload, 后续帧 PATCH 更新
- `seat_defect_core/fusion.py` — 跨相机 identity 合并
- `seat_defect_core/serialization.py` — 序列化 identity_id + unified_embedding
- `seat_defect_core/core_types/results.py` — 新增 identity_id
- `seat_defect_core/config.py` — 新增 TrackConfig
- `seat_defect_core/classifier/engine.py` — Filter 接收 unified_emb
- `ml/classifier/dual_modal/model.py` — 三路融合 (image + EAD raw + unified_emb)
- `backend/app/workers/embedding_worker/tasks.py` — 新增 alignment embedding 任务

### 关键设计约束

1. **协议与实现分离**: Contract 在 `defect_protocol/`，实现在各自模块
2. **Canonical Schema**: schema_version + 归一化坐标 + __post_init__ 验证 → 零漂移
3. **冲突显式化**: 所有 Identity 冲突有明确策略，无隐式行为
4. **Budget 作用域明确**: BudgetScope 枚举定义控制边界
