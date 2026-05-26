# EfficientAD 替代 PatchCore — 设计规格

## 目标

将 seat_defect_core 中的 PatchCore 纹理异常检测模块完整替换为 EfficientAD，同步调整前后端及配置文件。

## 范围

移除所有 PatchCore 相关代码和配置，用 anomalib 的 EfficientAD 实现替代，不保留共存模式。

## 变更清单

### 1. seat_defect_core — 移除

| 路径 | 说明 |
|---|---|
| `patchcore/__init__.py` | 模块入口 |
| `patchcore/engine.py` | `PatchCoreService`, `LoadedModelBundle` |
| `patchcore/features.py` | `_TorchPatchFeatureExtractor`, handcrafted 特征提取 |
| `patchcore/scoring.py` | coreset 采样, 距离计算, 异常判定, 热力图归一化 |
| `patchcore/color_branch.py` | `ColorReferenceProfile`, `ColorConsistencyService` |
| `training/patchcore.py` | `train_patchcore`, `train_patchcore_cli` |

### 2. seat_defect_core — 新增

#### `efficientad/__init__.py`

公开出口：`EfficientADService`, `EfficientADConfig`

#### `efficientad/config.py`

```python
@dataclass
class EfficientADConfig:
    model_path: str                              # .pt 模型文件路径
    device: str = "cpu"                          # cpu / cuda / mps
    input_size: int = 256                        # 输入尺寸
    teacher_backbone: str = "wide_resnet50_2"    # 教师网络
    student_backbone: str = "resnet18"           # 学生网络
    # 推理控制
    min_valid_pixel_ratio: float = 0.3           # 有效像素最低比例
    # 阈值
    threshold: float = 0.0                       # 训练时填充
    anomaly_score_threshold: float = 0.5         # 异常分数判定阈值
```

#### `efficientad/engine.py`

`EfficientADService` 类，提供：

- `__init__(config: EfficientADConfig)` — 加载 TorchScript 模型，对齐 anomalib 导出格式
- `predict(image, target_mask, ignore_mask) -> TextureAnomalyResult` — 单张推理，掩膜区域外填零
- `predict_batch(items: List[...]) -> List[TextureAnomalyResult]` — 批量推理
- `load_bundle(model_path) -> EfficientADService` — 从路径加载模型
- 输入预处理：resize → normalize（ImageNet 统计量）
- 输出后处理：anomaly_map → 双线性插值回原始尺寸 → threshold 判定

#### `training/efficientad.py`

基于 anomalib 的 EfficientAD 训练入口：

- `train_efficientad_cli()` — CLI 命令 `train-efficientad`
- 从 anomalib 加载 EfficientAD 模型和训练 pipeline
- 用正常图像训练后导出 TorchScript 模型
- 保存阈值元数据到模型文件

### 3. seat_defect_core — 修改

#### `config.py`

- 移除 `PatchCoreConfig`
- `CameraConfig` 中 `patchcore: PatchCoreConfig` → `efficientad: EfficientADConfig`
- `CameraConfig` 中 `patchcore_model_path` → `efficientad_model_path`
- `RegionConfig` 中 `patchcore_model_path` → `efficientad_model_path`
- `RegionConfig` 中 `patchcore: Optional[PatchCoreConfig]` → `efficientad: Optional[EfficientADConfig]`
- 移除 `ColorBranchConfig` 和 `ColorConsistencyService` 相关内容（颜色分支独立于纹理检测，但如果与 PatchCore 强耦合则移除；分析后发现 `color_branch.py` 在 patchcore 目录内，一起移除）

#### `core_types/results.py` — `TextureAnomalyResult`

精简为通用字段：

```python
@dataclass
class TextureAnomalyResult:
    score: float                    # 图像级异常分数 (0-1)
    threshold: float                # 判定阈值
    is_anomaly: bool                # 是否异常
    heatmap: Any                    # 原始尺寸异常热力图
    anomaly_map: Any                # 模型原始输出异常图
    valid_pixel_ratio: float = 1.0  # 有效像素比例
```

移除 PatchCore 特有字段：`valid_patch_count`, `total_patch_count`, `decision_threshold`, `peak_patch_score`, `strong_patch_count`, `strong_patch_ratio`, `largest_component_patch_count`, `decision_mode` 等。

#### `core_types/pipeline.py`

移除 `ColorAnomalyResult`（颜色分支随 patchcore/color_branch.py 移除）。

移除 `RegionPatchCoreResult`，重命名为 `RegionAnomalyResult`（字段中 patchcore_model_path → efficientad_model_path）。

保留 `FilterClassifierResult` 和 `FilterClassifierConfig`：过滤器分类器逻辑独立于 PatchCore，仅消费 `TextureAnomalyResult.is_anomaly`，适配后继续工作。

#### `service/core.py`

- 移除 `from ..patchcore import LoadedModelBundle, PatchCoreService`
- 新增 `from ..efficientad import EfficientADService`
- `LoadedModelBundle` → `LoadedAnomalyModel`（只包含 efficientad: EfficientADService）
- `PatchCorePredictorPool` → `EfficientADPredictor`（简化，无需跨相机共享 backbone）
- `ModelBundleCache` → `AnomalyModelCache`（缓存 EfficientADService 实例）
- `warmup()` 方法适配 EfficientAD

#### `service/inspection_camera.py`

- `RegionPatchCorePlan` → `RegionAnomalyPlan`，字段 `patchcore_items` → `anomaly_items`
- 移除 `_predict_color_branch`（颜色分支随 patchcore 移除）
- `_predict_filter_classifier` 保留，适配新 `TextureAnomalyResult` 字段
- `apply_rules` 调用保留，适配新 `TextureAnomalyResult` 字段
- `finish_region_patchcore_plan` → `finish_region_anomaly_plan`
- `_merge_region_status` 简化逻辑：只用 `quality_rejected` 和 `texture_result.is_anomaly`

#### `service/response.py`

- 调试产物生成移除 PatchCore 特定热力图叠加

#### `__main__.py`

- 移除 `train-patchcore` 子命令
- 新增 `train-efficientad` 子命令

#### `serialization.py`

- 序列化逻辑适配精简后的 `TextureAnomalyResult`
- 移除 `ColorAnomalyResult` 序列化

#### `anomaly_uploader.py`

- 兼容新的 `TextureAnomalyResult` 结构

#### `fusion.py`

- 多机位融合判定不受影响（仅消费 `CameraInspectionResult.status`）

#### `rule_engine.py`

- 保留但简化：texture_result 字段访问适配新结构
- 移除 `strong_patch_count` 等条件（如有引用）

#### `config.example.json`

- `cameras[].patchcore` → `cameras[].efficientad`
- `cameras[].patchcore_model_path` → `cameras[].efficientad_model_path`
- 移除 `color_branch` 块
- `cameras[].filter_classifier` → 保留，适配新 TextureAnomalyResult
- `cameras[].rule_engine` → 保留，适配新 TextureAnomalyResult
- `cameras[].regions[].patchcore_model_path` → `efficientad_model_path`

#### `config.training.example.json`

- 适配新的 EfficientAD 训练参数

#### `config.closed_loop_test.json`

- 同步上述 JSON 配置变更

#### `pyproject.toml`

- 新增依赖：`anomalib>=1.0.0`
- 移除 FAISS 依赖（EfficientAD 不需要 memory bank 搜索）

### 4. backend 变更

#### 重命名

| 原路径 | 新路径 |
|---|---|
| `app/schemas/patchcore_training.py` | `app/schemas/efficientad_training.py` |
| `app/api/patchcore_training/` | `app/api/efficientad_training/` |
| `app/workers/patchcore_training_worker/` | `app/workers/efficientad_training_worker/` |

#### `app/schemas/efficientad_training.py`

```python
class EfficientADTrainingStartRequest(BaseModel):
    camera_id: str
    config_json: str                       # 序列化的检测配置
```

（与 PatchCore 训练请求相同，仅类名变了）

#### `app/api/efficientad_training/router.py`

- 路由前缀 `/api/efficientad-training`
- 端点 `POST /start` — 上传正常图像、下发 Celery 任务
- 引用 `train_efficientad_model` 任务

#### `app/workers/efficientad_training_worker/tasks.py`

- Celery 任务 `train_efficientad_model`
- subprocess 调用 `seat_defect_core train-efficientad`
- 模型输出格式 `.pt` 替代 `.npz`
- `model_type="efficientad"` 写入 `ModelVersion`

#### `app/models/training.py`

- 无 Schema 变更，`model_type` 字段新增有效值 `"efficientad"`

### 5. frontend 变更

#### 重命名

| 原路径 | 新路径 |
|---|---|
| `src/types/patchcore-training.ts` | `src/types/efficientad-training.ts` |
| `src/api/patchcore-training.ts` | `src/api/efficientad-training.ts` |

#### `src/api/efficientad-training.ts`

- 端点从 `/patchcore-training/start` 改为 `/efficientad-training/start`

#### `src/hooks/queries.ts`

- `usePatchCoreTrainingStart` → `useEfficientADTrainingStart`
- Hook 内部实现适配新的 API 端点

#### `src/features/training/index.tsx`

- Tab 标签 "PatchCore 训练" → "EfficientAD 训练"
- 表单变量重命名
- 引用 `useEfficientADTrainingStart`
- 模型类型 Tag 颜色 `"efficientad"` → 新颜色（如 cyan）

#### `src/features/training/components/TaskLogPanel.tsx`

- 任务日志中 `patchcore` → `efficientad` 相关的识别逻辑

## 数据迁移

- 现有 `.npz` PatchCore 模型文件不再可用，需重新用正常图像训练 EfficientAD 模型
- `ModelVersion` 表中 `model_type="patchcore"` 的历史记录可保留，前端列表展示时做兼容处理
- 在线端的配置文件需手动更新为新的 `efficientad` 块

## 不在范围内的内容

- YOLO 检测模块变更
- ROI 提取和图像质量检测变更
- 多机位融合策略变更
- 过滤器分类器和规则引擎的重建（保留并适配新接口，不新增功能）

## 风险

| 风险 | 缓解 |
|---|---|
| EfficientAD 在真实工业场景精度不如 PatchCore | 迁移后对比测试，保留降级方案（git 历史中的 PatchCore 代码） |
| anomalib 依赖体积大 | pyproject.toml 中只声明 anomalib 核心依赖，避免引入不必要的子包 |
| TorchScript 模型跨设备兼容性 | 训练时导出 CPU 版本，推理时按 device 加载 |
| 热力图可视化差异 | EfficientAD 输出像素级 anomaly_map，可视化按原 heatmap 逻辑处理 |
