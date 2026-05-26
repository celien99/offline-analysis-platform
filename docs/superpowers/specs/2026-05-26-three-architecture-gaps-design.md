# Three Architecture Gaps: Budget Controller + Identity Linking + Unified Embedding

**日期**: 2026-05-26
**状态**: 设计完成，待实现
**前置**: EfficientAD → Filter Architecture Upgrade (2026-05-26)

## 动机

基于上一轮架构升级，发现三个工程薄弱点：

1. **Proposal 数量不可控**：噪声纹理（织物纹路）可产生 100+ CCs，计算开销在截断前已全部发生，最坏情况延迟不可预测
2. **无 Defect Identity**：每帧 proposal 独立，同一缺陷跨帧/跨相机产生 N 个 anomaly_record，污染聚类和训练数据
3. **Embedding 空间分裂**：在线用 EfficientAD 特征（多尺度 spatial），离线用 DINOv2（384d），两个空间完全独立，聚类发现无法指导在线判定

## 改进 1: Proposal Budget Controller

### 三态策略

| 模式 | 触发条件 | 行为 |
|---|---|---|
| **Normal** | elapsed < 15ms | 完整 pipeline，K 由剩余预算动态决定 |
| **Emergency** | elapsed ≥ 20ms **或** CC count ≥ 50 | Early exit，跳过 Filter，未处理 proposal 标记 is_real_defect=True |
| **Optimization** | 最近 100 帧平均 proposal 数 > 目标 | 持久化提高 adaptive_threshold_multiplier（1.5→2.0→2.5），缓慢恢复 |

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
- 新增: `seat_defect_core/proposal/budget.py` (BudgetController)
- 修改: `proposal/config.py` (BudgetConfig), `proposal/generator.py` (集成 regulate())

## 改进 2: Defect Identity Linking

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
| Stage 2 | EfficientAD teacher_l3 余弦相似度 | 同相机重识别 + 跨相机关联 | cosine≥0.85 |
| Stage 3 | 几何约束验证 | 跨相机后验证 | epipolar distance≤50px |

### 去重策略

- MATURE (≥5帧) → 选择 best frame (max anomaly_score) 作为代表上传
- 同一 identity 后续帧有更好视角 → PATCH 更新已有 anomaly_record
- 跨相机 identity 合并 → 同一 identity_id，fusion 只计一次

### Kalman 运动模型

6-DOF: (x, y, w, h, vx, vy)，匀速模型，标准 Kalman predict/update。

### 文件改动
- 新增: `seat_defect_core/tracking/` (identity.py, tracker.py, matcher.py, kalman_filter.py, config.py)
- 修改: `inspection_camera.py`, `anomaly_uploader.py`, `core_types/results.py`, `fusion.py`

## 改进 3: Unified Embedding Space (Teacher-Student Alignment)

### 架构

```
EfficientAD Teacher Features (l1/l2/l3/diff)
    → Per-Layer GAP + FC(128) → Concat (512d)
    → Transformer Encoder (2 layers, 4 heads, FFN 1024)
    → FC(384) → L2 Norm
    → Unified Embedding (384d, DINOv2-compatible geometry)
```

### 训练

- **Loss**: InfoNCE (Contrastive), τ=0.07
- **正样本**: (EAD_proj, DINOv2) 同一 anomaly
- **负样本**: batch 内其他 anomaly 的 DINOv2
- **数据**: 从已审核异常收集成对 (EAD features, DINOv2 embedding)
- **优化器**: AdamW, lr=1e-4, cosine schedule
- **导出**: TorchScript，在线推理加载

### 四大消费者

| 消费者 | 用法 | 说明 |
|---|---|---|
| 离线聚类 | DINOv2 → UMAP → HDBSCAN | 不变，DINOv2 是 target geometry |
| Dual-Modal Filter | unified_emb 作为额外输入 | image + EAD raw + unified_emb 三路融合 |
| DefectTracker | 跨帧/跨相机特征匹配 | cosine_sim 做 identity 关联 |
| 异常检索 | pgvector 相似度查询 | 在线 proposal 直接检索离线知识库 |

### Embedding Space Contract

```python
# defect_protocol/embedding_space.py
@dataclass
class UnifiedEmbedding:
    vector: list[float]  # 384-dim, L2 normalized
    model_version: str   # projector model version
    source: str          # "efficientad_projected" | "dinov2"

@dataclass  
class EmbeddingSpace:
    dim: int = 384
    norm: str = "l2"
    similarity: str = "cosine"
    target_geometry: str = "dinov2_vits14"
```

### 文件改动
- 新增: `ml/alignment/` (projector.py, trainer.py, dataset.py, config.py)
- 新增: `defect_protocol/embedding_space.py`
- 修改: `classifier/engine.py`, `dual_modal/model.py` (三路融合), `tracking/matcher.py`, `embedding_worker/tasks.py`

## 完整文件改动清单 (21 files)

### 新增 (11)
- `seat_defect_core/proposal/budget.py`
- `seat_defect_core/tracking/` (identity.py, tracker.py, matcher.py, kalman_filter.py, config.py)
- `ml/alignment/` (projector.py, trainer.py, dataset.py, config.py)
- `defect_protocol/embedding_space.py`

### 修改 (10)
- `seat_defect_core/proposal/config.py` — 新增 BudgetConfig
- `seat_defect_core/proposal/generator.py` — 集成 BudgetController
- `seat_defect_core/service/inspection_camera.py` — 接入 Identity Linking
- `seat_defect_core/anomaly_uploader.py` — MATURE identity → upload, PATCH 更新
- `seat_defect_core/fusion.py` — 跨相机 identity 合并
- `seat_defect_core/serialization.py` — 序列化 identity_id
- `seat_defect_core/core_types/results.py` — PatchProposal 新增 identity_id
- `seat_defect_core/config.py` — 新增 TrackConfig
- `seat_defect_core/classifier/engine.py` — Filter 接收 unified_emb
- `ml/classifier/dual_modal/model.py` — 三路融合 (image + EAD raw + unified_emb)
