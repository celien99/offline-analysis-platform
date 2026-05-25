# 相机配置页面 & 检测页面联动

## 概述

新增相机配置管理页面，配置数据存数据库；检测页面的相机选择改为下拉框模式，联动配置数据。

## 数据模型

### seat_models 表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID, PK | 主键 |
| seat_model_id | varchar, unique, not null | 座椅型号标识符（如 seat_model_a） |
| display_name | varchar, not null | 前端显示名称 |
| created_at | datetime | |
| updated_at | datetime | |
| deleted_at | datetime, nullable | 软删除 |

### camera_configs 表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID, PK | 主键 |
| camera_id | varchar, not null | 相机标识符 |
| seat_model_id | varchar, FK → seat_models | 所属座椅型号 |
| patchcore_model_path | varchar, not null | 整体 PatchCore 模型路径 |
| yolo_model_path | varchar, not null | YOLO 检测模型路径 |
| detection_confidence | float, default 0.25 | YOLO 置信度 |
| patchcore_image_size | int, default 256 | PatchCore 输入尺寸 |
| patchcore_threshold | float, default 0.99 | PatchCore 异常阈值分位数 |
| region_mode_enabled | bool, default false | 是否开启三分区模式 |
| region_upper_model_path | varchar, nullable | upper 区域 PatchCore 模型 |
| region_middle_model_path | varchar, nullable | middle 区域 PatchCore 模型 |
| region_lower_model_path | varchar, nullable | lower 区域 PatchCore 模型 |
| created_at | datetime | |
| updated_at | datetime | |
| deleted_at | datetime, nullable | 软删除 |

唯一约束：同一 seat_model 下 camera_id 唯一。

## 后端 API

### 座椅型号

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /api/seat-models | 列表（分页） |
| POST | /api/seat-models | 新建 |
| PUT | /api/seat-models/{id} | 编辑 |
| DELETE | /api/seat-models/{id} | 软删除 |
| GET | /api/seat-models/options | 下拉选项，含关联相机列表 |

### 相机配置

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /api/seat-models/{model_id}/cameras | 某型号下的相机列表 |
| POST | /api/seat-models/{model_id}/cameras | 新建相机 |
| PUT | /api/seat-models/{model_id}/cameras/{id} | 编辑相机 |
| DELETE | /api/seat-models/{model_id}/cameras/{id} | 软删除 |

## 检测流程改造

检测时，后端不再依赖 `config.example.json`，而是：

1. 从数据库读取选中相机的配置
2. 用默认参数填充 YOLO/ROI/PatchCore/Filter/Color/Rule 等底层配置
3. 生成完整 config JSON，写入临时文件
4. 将临时配置文件路径传给 `seat_defect_core` 子进程

默认参数模板定义在后端代码中（复制现有 config.example.json 中各段的默认值）。

## 前端页面

### 相机配置页面 `/cameras`

- 路由：`/cameras`
- 布局：左侧座椅型号列表 + 右侧相机配置表格
- 座椅型号：可新增、编辑、删除
- 相机配置：表格列 = camera_id / YOLO模型 / PatchCore模型 / Region模式(是/否) / 操作
- 新建/编辑相机弹窗：
  - 基本字段：camera_id、patchcore_model_path、yolo_model_path
  - 高级参数折叠面板：detection_confidence、patchcore_image_size、patchcore_threshold
  - Region 模式开关 → 展开 upper/middle/lower 三个模型路径输入框

### 检测页面改造 `/inspection`

- 新增 Step 1：选择座椅型号（下拉单选）
- 新增 Step 2：勾选该型号下的相机（多选复选框，数据从 GET /api/seat-models/options 获取）
- Step 3：每个选中的相机生成一个图像上传槽位
- 移除手动输入相机 ID、手动"添加相机"按钮

## 安全约束

- YOLO/PatchCore 底层参数（backbone、stride、ROI、Filter Classifier、Rule Engine 等）不在前端暴露，仅后端默认值控制
- 所有 API 参数需做基本校验（camera_id 格式、路径合法性）
- 软删除保留历史数据

## 技术实现要点

- 后端：FastAPI + SQLAlchemy + Repository 模式 + Pydantic Schema + Alembic 迁移
- 前端：React + Ant Design（Table、Modal、Form、Select、Switch 等组件）
- 检测时动态生成配置 JSON 的函数放在 `app/services/inspection/` 下
