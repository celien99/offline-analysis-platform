# 离线分析平台 — 标准操作流程 (SOP)

> 本文档覆盖离线分析平台（第 1~9 章）和在线检测核心 seat_defect_core（第 10 章）的完整操作流程。

## 1. 系统概述

本平台是一个 **工业 AI 离线智能分析平台**，面向汽车座椅缺陷检测场景。它与线上实时检测系统（YOLO + PatchCore + Filter Classifier）配合运行，但**自身不参与线上实时判定**，而是作为"AI 进化大脑"持续学习线上采集的异常样本，通过聚类分析、VLM 解释、人工审核、知识沉淀和模型训练，反哺线上系统以**持续降低误报率**。

### 1.1 核心业务流程

```
线上检测系统 → 异常样本上传 → 特征提取(DINOv2-S) → 无监督聚类(UMAP+HDBSCAN)
                                                              ↓
线上部署 ← 模型训练 ← 知识库构建 ← 人工审核(6种操作) ← VLM自动分析
```

### 1.2 技术栈速览

| 层级 | 技术 |
|------|------|
| 后端 API | FastAPI (async) |
| 异步任务 | Celery + Redis |
| 数据库 | PostgreSQL 16 + pgvector (向量相似搜索) |
| 对象存储 | MinIO |
| 模型注册 | MLflow |
| 前端 | React + Ant Design + Plotly |
| ML | PyTorch, DINOv2-S, UMAP, HDBSCAN, Qwen2.5-VL/InternVL |

---

## 2. 环境搭建

### 2.1 前置条件

- Docker Desktop 或 Docker Engine
- Python 3.11 + uv 包管理器
- Node.js 18+
- （可选）NVIDIA GPU + nvidia-container-toolkit（用于 Worker 的 GPU 加速）

### 2.2 启动基础设施服务

基础设施（PostgreSQL、Redis、MinIO、MLflow）通过 Docker Compose 启动：

```bash
cd backend
docker compose up -d db redis minio minio-init mlflow
```

验证所有服务正常运行：

```bash
docker compose ps
# 应看到 db(healthy)、redis(healthy)、minio(healthy)、mlflow(running)
```

服务端口映射：

| 服务 | 端口 | 访问地址 |
|------|------|----------|
| PostgreSQL (pgvector) | 5432 | `postgres://postgres:postgres@localhost:5432/anomaly_db` |
| Redis | 6379 | `redis://localhost:6379` |
| MinIO (S3 API) | 9000 | `http://localhost:9000` |
| MinIO Console (Web UI) | 9001 | `http://localhost:9001` (账号: `minioadmin` / `minioadmin`) |
| MLflow | 5001 | `http://localhost:5001` |

### 2.3 启动后端

```bash
cd backend

# 1. 复制环境配置
cp .env.example .env

# 2. 安装依赖
uv sync

# 3. 运行数据库迁移
uv run alembic upgrade head

# 4. 启动 API 服务 (开发模式)
uv run uvicorn app.main:app --reload --port 8000
```

API 文档访问：
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### 2.4 启动 Celery Worker（可选，用于执行异步 ML 任务）

```bash
cd backend
uv run celery -A app.infrastructure.queue.celery_app worker -l info -c 2
```

### 2.5 启动前端

```bash
cd frontend
npm install
npm run dev
# 访问 http://localhost:3000，API 请求自动代理到 :8000
```

---

## 3. 端到端操作流程

### 阶段一：上传异常样本

**场景：** 线上检测系统发现可疑样本后，通过 API 上传到此平台进行离线分析。

#### 3.1.1 通过 Web UI 上传

1. 打开 `http://localhost:3000/upload`
2. 填写表单：
   - **Camera ID**: 相机编号（如 `CAM-01`）
   - **Date Folder**: 日期文件夹（格式 `YYYY-MM-DD`）
   - **Source**: 来源系统，可选 `patchcore` / `filter_classifier` / `rule_engine`
   - **Anomaly Score**: 异常分数（PatchCore 欧氏距离值，通常 >0，无上限）
   - **Detected At**: 检测时间
3. 上传图像文件（至少提供一张）：
   - **Original Image**: 原始大图
   - **ROI Image**: 感兴趣区域裁剪
   - **Heatmap**: 热力图
   - **Crop Image**: 异常区域裁剪（**这是后续特征提取的关键图像**）
4. 点击提交

#### 3.1.2 通过 API 上传

```bash
# 带文件的 multipart 上传
curl -X POST http://localhost:8000/api/anomaly/upload-with-files \
  -F "camera_id=CAM-01" \
  -F "date_folder=2026-05-22" \
  -F "source=patchcore" \
  -F "anomaly_score=0.85" \
  -F "detected_at=2026-05-22T10:30:00" \
  -F "crop_file=@/path/to/crop.jpg"

# JSON 元数据上传（适用于图像已通过其他方式上传到 MinIO 的场景）
curl -X POST http://localhost:8000/api/anomaly/upload \
  -H "Content-Type: application/json" \
  -d '{
    "camera_id": "CAM-01",
    "source": "patchcore",
    "anomaly_score": 0.85,
    "date_folder": "2026-05-22",
    "detected_at": "2026-05-22T10:30:00"
  }'
```

#### 3.1.3 上传后验证

1. 打开 `http://localhost:3000/anomalies` 查看已上传的异常列表
2. 确认状态显示为 `pending`（表示等待特征提取）
3. 点击某条记录可查看详情和预签名图像 URL

### 阶段二：特征提取与聚类

**场景：** 对积累的异常样本进行特征提取和无监督聚类，自动发现相似异常模式。

#### 3.2.1 手动触发聚类

打开 `http://localhost:8000/docs`，调用 `POST /api/cluster/trigger`：

```json
{
  "min_cluster_size": 10,
  "min_samples": 5,
  "anomaly_ids": []
}
```

- 如果 `anomaly_ids` 为空，系统会自动获取所有 `pending` 状态的异常进行聚类
- 返回 `task_id` 后，可通过 Celery 监控任务进度

#### 3.2.2 自动触发（Celery Beat 定时任务）

生产环境中，Celery Beat 每 6 小时自动执行 `pipeline.full_cycle`，包含：
1. `process_new_anomalies` — 对新异常执行嵌入提取
2. 聚类运行
3. `trigger_vlm_on_new_clusters` — 对新聚类执行 VLM 分析

#### 3.2.3 流水线详细步骤

| 步骤 | 输入 | 处理 | 输出 |
|------|------|------|------|
| 特征提取 | MinIO 中的 crop 图像 | DINOv2-S → 384 维向量 | pgvector 存储的 EmbeddingVector |
| 降维 | 全部嵌入向量 | StandardScaler → UMAP (2D) | 2D 坐标 |
| 聚类 | 降维后的向量 | HDBSCAN | 聚类分组 + 噪声标签 |
| 持久化 | 聚类结果 | 写入 DB | Cluster + ClusterMembership |

### 阶段三：聚类审核（核心人工环节）

**场景：** 工程师通过 Web UI 审查 AI 自动生成的聚类，判断每个聚类是真实缺陷还是误报。

#### 3.3.1 进入聚类审核页面

打开 `http://localhost:3000/clusters`

页面展示：
- **左侧筛选栏**：按审核状态（全部/待审核/已确认缺陷/已确认误报）、缺陷类型、VLM 判定筛选
- **主表格**：聚类列表，包含名称、样本量、VLM 分析结果、审核状态、操作按钮
- **上方统计卡片**：总聚类数、总样本数、真实缺陷数、误报数、待审核数

#### 3.3.2 查看聚类详情

点击某个聚类的"详情"按钮，会弹出弹窗展示：

- **代表图像**：该聚类中最具代表性的异常图像（按 HDBSCAN 概率排序的前 5 张）
- **VLM 分析结果**：大模型对该聚类的自动解读，包括：
  - 疑似异常类型（`anomaly_type`）
  - 是否为误报（`is_false_alarm`）
  - 判定理由（`reason`）
  - 置信度（`confidence`）
  - 处理建议（`suggestion`）
- **成员列表**：聚类中的所有异常样本
- **聚类统计**：出现频次、关联相机、时间分布

#### 3.3.3 执行审核操作（6 种操作）

| 操作 | 说明 | 后果 |
|------|------|------|
| **确认缺陷** (confirm_defect) | 确认此聚类为真实缺陷 | 可选填缺陷类型（折痕/划痕/反光/污渍/缝线偏移），自动生成知识库条目，后续可作为分类器训练的正样本 |
| **标记误报** (mark_false_alarm) | 标记此聚类为误报 | 自动生成知识库条目（category=false_alarm），后续可作为分类器训练的负样本 |
| **重命名** (rename) | 重命名聚类 | 便于后续搜索和识别 |
| **拆分** (split) | 将选中的异常成员从当前聚类中分离，创建新的子聚类 | 当某聚类中混入了不同类型的异常时使用 |
| **合并** (merge) | 将其他聚类的异常合并到当前聚类 | 当多个聚类实际上是同一类型时使用 |
| **忽略** (ignore) | 忽略此聚类 | 标记为 false_alarm，不生成知识库条目 |

#### 3.3.4 API 方式提交审核

```bash
# 确认缺陷
curl -X POST http://localhost:8000/api/cluster/review \
  -H "Content-Type: application/json" \
  -d '{
    "cluster_id": "abc123...",
    "reviewer": "engineer-zhang",
    "action": "confirm_defect",
    "defect_type": "scratch"
  }'

# 标记误报
curl -X POST http://localhost:8000/api/cluster/review \
  -H "Content-Type: application/json" \
  -d '{
    "cluster_id": "def456...",
    "reviewer": "engineer-zhang",
    "action": "mark_false_alarm"
  }'

# 拆分聚类
curl -X POST http://localhost:8000/api/cluster/review \
  -H "Content-Type: application/json" \
  -d '{
    "cluster_id": "abc123...",
    "reviewer": "engineer-zhang",
    "action": "split",
    "split_member_ids": ["anomaly-id-1", "anomaly-id-2"]
  }'

# 合并聚类
curl -X POST http://localhost:8000/api/cluster/review \
  -H "Content-Type: application/json" \
  -d '{
    "cluster_id": "target-123...",
    "reviewer": "engineer-zhang",
    "action": "merge",
    "merge_source_ids": ["source-456...", "source-789..."]
  }'
```

### 阶段四：知识库管理

**场景：** 审核完成后，系统自动生成知识库条目。工程师也可手动补充知识条目。

#### 3.4.1 查看自动生成的知识

打开 `http://localhost:3000/knowledge`

- 系统在确认缺陷或标记误报时**自动生成**知识条目
- 条目包含：分类（defect/false_alarm/camera_issue/lighting/process）、缺陷类型、建议动作（ignore/NG/review_required）、关联相机

#### 3.4.2 手动创建知识条目

```bash
curl -X POST http://localhost:8000/api/knowledge/entries \
  -H "Content-Type: application/json" \
  -d '{
    "title": "CAM-02 反光误报",
    "category": "false_alarm",
    "defect_type": "reflection",
    "action": "ignore",
    "camera_ids": ["CAM-02"],
    "description": "CAM-02 特定角度金属件反光，参数调整后可消除"
  }'
```

#### 3.4.3 搜索知识库

```bash
# 全文搜索
curl "http://localhost:8000/api/knowledge/entries/search?q=反光"
```

### 阶段五：规则引擎

**场景：** 将沉淀的知识转化为可执行的规则，供线上系统过滤已知误报。

#### 3.5.1 从知识条目生成规则

在 `http://localhost:3000/knowledge` 页面，点击某个知识条目后的"生成规则"按钮。

或通过 API：

```bash
curl -X POST "http://localhost:8000/api/rules/generate-from-knowledge?knowledge_entry_id=<entry-id>"
```

#### 3.5.2 管理规则

打开 `http://localhost:3000/rules`

- 查看、创建、启用/禁用规则
- 每条规则包含：
  - **类型**：ignore（忽略）/ flag（标记）/ escalate（升级）
  - **优先级**：数字越大越优先
  - **条件 JSON**：如 `{"camera_id": "CAM-01", "predicted_class": "reflection"}`
  - **关联相机**：规则适用的相机列表

#### 3.5.3 评估规则效果

```bash
# 模拟评估：给定输入，查看规则引擎的输出动作
curl -X POST "http://localhost:8000/api/rules/evaluate?camera_id=CAM-01" \
  -H "Content-Type: application/json" \
  -d '{
    "camera_id": "CAM-01",
    "anomaly_score": 0.6,
    "predicted_class": "reflection",
    "defect_type": null
  }'
```

### 阶段六：分类器训练

**场景：** 当积累了足够多的已审核样本（正负例）后，训练新的 Filter Classifier 来替代线上旧模型。

#### 3.6.1 启动训练

打开 `http://localhost:3000/training`，点击"开始训练"，选择模型类型和超参数：

| 可选模型 | 特点 |
|----------|------|
| MobileNetV3-Small（默认） | 轻量级，适合边缘部署 |
| EfficientNet-B0 | 精度与速度平衡 |
| ResNet18 | 通用分类 backbone（与 DINOv2 嵌入独立） |

或通过 API：

```bash
curl -X POST http://localhost:8000/api/training/start \
  -H "Content-Type: application/json" \
  -d '{
    "architecture": "mobilenet_v3_small",
    "learning_rate": 0.001,
    "batch_size": 32,
    "epochs": 50
  }'
```

#### 3.6.2 监控训练进度

- 前端页面每 5 秒轮询训练状态
- 通过 MLflow UI (`http://localhost:5001`) 查看训练指标曲线（loss、accuracy）
- API 查询：`GET /api/training/status/{task_id}`

#### 3.6.3 训练完成后

- 模型以 TorchScript 和 ONNX 格式导出
- 自动注册到 MLflow，可通过 `http://localhost:5001` 查看
- 在 `http://localhost:3000/training` 的模型列表中可见

### 阶段七：模型部署

**场景：** 将训练好的模型部署到线上检测系统的指定目标环境。

#### 3.7.1 部署模型

打开 `http://localhost:3000/deploy`，选择模型版本和目标环境，点击部署。

或通过 API：

```bash
curl -X POST http://localhost:8000/api/model/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "model_version_id": "<version-id>",
    "target": "production-line-1",
    "deployed_by": "engineer-zhang"
  }'
```

#### 3.7.2 回滚

如果新部署的模型效果不佳，可以快速回滚到上一版本：

```bash
curl -X POST "http://localhost:8000/api/model/deploy/production-line-1/rollback"
```

### 阶段八：Dashboard 总览

打开 `http://localhost:3000/` 查看系统总览：

- **UMAP 散点图**：全部聚类的 2D 可视化分布，不同颜色表示不同审核状态
- **审核状态柱状图**：各状态聚类的数量分布
- **统计卡片**：总聚类数、总样本数、真实缺陷数、误报数、待审核数

### 阶段九：相似异常搜索

打开 `http://localhost:3000/anomalies`，点击某个异常：
1. 使用"相似搜索"功能，通过向量相似度查找 Top-K 个最相似的异常
2. API：`POST /api/embedding/search` 或 `GET /api/embedding/search?anomaly_id=xxx&top_k=10&threshold=0.7`

---

## 4. 典型工作场景速查

### 场景 A：新异常入库 → 人工审核 → 生成知识

```
1. [线上系统] POST /api/anomaly/upload-with-files     ← 上传异常样本
2. [自动/手动] POST /api/cluster/trigger              ← 触发聚类
3. [Web UI]    /clusters → 查看聚类 → 执行审核操作    ← 人工审核
4. [自动]      系统自动生成 KnowledgeEntry            ← 知识沉淀
5. [Web UI]    /knowledge → 查看/搜索知识条目         ← 知识管理
```

### 场景 B：误报过滤规则上线

```
1. [Web UI]    /knowledge → 找到误报相关条目 → "生成规则"
2. [Web UI]    /rules → 启用规则
3. [API]       POST /api/rules/evaluate → 验证规则效果
4. [线上系统]  同步规则配置 → 滤除已知误报
```

### 场景 C：训练新分类器并部署

```
1. 确认积累了足够的已审核样本
2. [Web UI]    /training → 启动训练
3. [MLflow]    http://localhost:5001 → 查看训练曲线
4. [Web UI]    /deploy → 选择模型版本 → 部署到目标环境
5. [线上系统]  加载新模型 → 误报率下降
```

---

## 5. 异常状态流转

```
pending ──→ processing ──→ embedded ──→ clustered ──→ pending_review ──→ reviewed
  │              │              │              │               │
  │              │              │              │               ├── real_defect   (确认为缺陷)
  │              │              │              │               └── false_alarm   (标记为误报)
  │              │              │              │
  │              │              │              └── noise         (HDBSCAN -1 标签, 不进入聚类)
  │              │              │
  │              │              └── 嵌入提取完成, 等待聚类
  │              │
  │              └── 嵌入提取失败或重新处理中
  │
  └── 上传后初始状态, 等待嵌入提取
```

---

## 6. 常见问题排查

### 6.1 上传异常后看不到数据

- 检查 MinIO 是否运行：`docker compose ps minio`
- 检查 MinIO 存储桶是否创建：访问 `http://localhost:9001` → Buckets → 应有 `anomaly-data`
- 检查 API 返回：`curl http://localhost:8000/api/anomaly/list`
- 查看后端日志中的错误信息

### 6.2 聚类触发后没有反应

- 确认有足够数量的 `pending` 状态异常（至少 ≥ `min_cluster_size`，默认 10）
- 检查 Celery Worker 是否运行：`ps aux | grep celery`
- 查看 Celery Worker 日志

### 6.3 VLM 分析不可用

- VLM 分析依赖外部 vLLM 服务（`INDUSTRIAL_VLM_ENDPOINT` 环境变量指向的服务）
- 如果不需要 VLM 分析，可以直接进行人工审核，VLM 结果为可选辅助功能

### 6.4 前端页面加载失败

- 确认后端 API 运行在 8000 端口
- 前端 dev server 会自动代理 `/api` 前缀请求到 `http://localhost:8000`
- 检查浏览器控制台是否有 CORS 错误

### 6.5 重置环境

```bash
# 完全清理并重建
cd backend
docker compose down -v      # 删除容器+数据卷
docker compose up -d db redis minio minio-init mlflow  # 重建基础设施
uv run alembic upgrade head                            # 重建表结构
```

---

## 7. 环境变量参考

所有环境变量前缀为 `INDUSTRIAL_`，定义在 `backend/.env` 文件中：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `INDUSTRIAL_POSTGRES_URL` | `postgresql+asyncpg://...` | 数据库连接串 |
| `INDUSTRIAL_REDIS_URL` | `redis://localhost:6379/0` | Redis 缓存 |
| `INDUSTRIAL_CELERY_BROKER_URL` | `redis://localhost:6379/1` | Celery 消息代理 |
| `INDUSTRIAL_CELERY_RESULT_BACKEND` | `redis://localhost:6379/2` | Celery 结果存储 |
| `INDUSTRIAL_MINIO_ENDPOINT` | `localhost:9000` | MinIO 服务地址 |
| `INDUSTRIAL_MINIO_ACCESS_KEY` | `minioadmin` | MinIO 访问密钥 |
| `INDUSTRIAL_MINIO_SECRET_KEY` | `minioadmin` | MinIO 密钥 |
| `INDUSTRIAL_MINIO_BUCKET` | `anomaly-data` | MinIO 存储桶名 |
| `INDUSTRIAL_MLFLOW_TRACKING_URI` | `http://localhost:5001` | MLflow 地址 |
| `INDUSTRIAL_EMBEDDING_MODEL` | `dinov2_vits14` | 嵌入模型 |
| `INDUSTRIAL_CLUSTERING_MIN_CLUSTER_SIZE` | `10` | HDBSCAN 最小聚类大小 |
| `INDUSTRIAL_CLUSTERING_MIN_SAMPLES` | `5` | HDBSCAN 最小样本数 |
| `INDUSTRIAL_VLM_ENDPOINT` | `http://localhost:8001/v1` | VLM 服务端点 |
| `INDUSTRIAL_DEBUG` | `false` | 调试模式开关 |

---

## 8. 关键端口速查

| 端口 | 服务 | 用途 |
|------|------|------|
| 8000 | FastAPI | 后端 API + Swagger 文档 |
| 3000 | Vite | 前端开发服务器 |
| 5432 | PostgreSQL | 数据库直连 |
| 6379 | Redis | 缓存 + 消息队列 |
| 9000 | MinIO | 对象存储 S3 API |
| 9001 | MinIO Console | 对象存储管理界面 |
| 5001 | MLflow | 模型实验追踪界面 |

---

## 9. 甲方工艺工程师日常操作指南

> **读者对象**：甲方产线工艺工程师。本章假设平台已由供应商部署完毕，线上检测系统已接入并持续上传异常样本。你不需要理解"聚类算法"或"向量数据库"——你只需要判断每张图到底是不是真缺陷。

### 9.1 你的角色：AI 的老师

整个离线平台的核心价值链条是：

```
异常样本自动收集 → AI 自动分组 → VLM 给出初步判断 → 你审核确认/纠正 → 系统学到知识 → 线上模型变聪明
```

你处在最关键的一环——**审核确认**。AI 负责"猜"，你负责"判"。你的每一次确认或纠正，都是 AI 学习的养料。没有你的判断，系统无法进化。

**你每天只需要做一件事**：打开聚类审核页面，对 AI 整理好的异常样本逐组做出判断。

### 9.2 你需要掌握的操作（共 6 种）

| 操作 | 使用频率 | 一句话说明 |
|------|----------|-----------|
| **确认缺陷** | ★★★★★ | "对，这批确实是缺陷，类型是 XXX" |
| **标记误报** | ★★★★☆ | "不对，这批是误报，全是反光/灰尘/角度问题" |
| **重命名** | ★★★☆☆ | "AI 取的名字不好，我改个有意义的" |
| **拆分** | ★★☆☆☆ | "这一组里混进了两种不同的东西" |
| **合并** | ★☆☆☆☆ | "这两个组其实是一种东西" |
| **忽略** | ★☆☆☆☆ | "这批没必要关注，无视" |

### 9.3 日常工作流（每天 15~30 分钟）

#### Step 1：登录

浏览器打开 `http://<平台IP>:3000/clusters`

#### Step 2：筛选待审核的聚类

页面左侧筛选栏，选择"审核状态 = 待审核"，点击查询。

#### Step 3：逐个审核聚类

对列表中每个聚类，执行以下判断流程：

---

#### 判断流程图

```
                      打开一个聚类
                           │
              查看代表图像 + VLM 分析结果
                           │
                    ┌──────┴──────┐
                    ↓              ↓
              图像上有肉眼         图像上**没有**
              可见的缺陷？         可见缺陷？
                    │              │
              ┌─────┴─────┐        │
              ↓           ↓        ↓
          缺陷清晰    缺陷模糊   标记误报
          可归类      不易归类   (mark_false_alarm)
              │           │
              ↓           ↓
         确认缺陷      确认缺陷
      (选具体类型)   (类型选"其他")
```

#### Step 4：记录审核结果

每完成一个聚类的审核，系统自动保存你的判断，并自动生成知识条目。

#### Step 5：关注统计数字

审核完成后回到 Dashboard 首页 (`/`)，检查：
- **待审核数**是否在持续下降（说明没有积压）
- **误报率**趋势（false_alarm / total）

### 9.4 各操作详细使用场景

#### 9.4.1 确认缺陷（confirm_defect）

**什么时候用**：代表图像上能清晰看到产品表面的真实异常。

**操作步骤**：
1. 点击聚类的"审核"按钮
2. 选择操作类型：**确认缺陷**
3. 选择缺陷类型（五选一）：

| 缺陷类型 | 特征描述 | 典型图像 |
|----------|----------|----------|
| **折痕 (crease)** | 面料表面呈线状压痕，通常沿固定方向，光照下有阴影 | 线状凹陷 |
| **划痕 (scratch)** | 面料/皮革表面被尖锐物划过，呈不规则线状，边缘可能有毛刺 | 不规则划伤 |
| **反光 (reflection)** | 金属件或光滑表面存在强反光区域，遮挡了真实表面 | 镜面反光斑块 |
| **污渍 (stain)** | 面料表面存在颜色异常的斑块或斑点，形状不规则 | 深色/浅色污迹 |
| **缝线偏移 (stitch_offset)** | 缝线偏离了标准位置，线迹不直或跳针 | 缝线歪斜 |

4. 可选填写备注（如"左侧扶手区域折痕，批次 20260520 多次出现"）
5. 点击提交

**审核后效果**：此聚类被标记为"真实缺陷"，系统中积累一个正样本。当正负样本积累足够后，供应商可训练新模型来更好地识别此类缺陷。

---

#### 9.4.2 标记误报（mark_false_alarm）

**什么时候用**：代表图像上**没有**产品表面的真实异常——AI 看错了。

**常见误报场景**：

| 误报原因 | 图像特征 | 是否可消除 |
|----------|----------|-----------|
| **金属件反光** | 特定角度的金属件出现镜面反光 | ✅ 可配置规则过滤 |
| **正常纹理变化** | 面料本身的纹理/图案被 AI 误判 | ⚠️ 需更多样本训练 |
| **相机脏污/灰尘** | 镜头或光源上有灰尘导致固定位置出现"伪异常" | ✅ 清洁相机即可 |
| **位置偏移** | ROI 框偏移导致截取了正常区域 | ✅ 调整 ROI 参数 |
| **光照变化** | 环境光变化导致图像亮度差异 | ⚠️ 需光学调整 |

**操作步骤**：
1. 点击聚类的"审核"按钮
2. 选择操作类型：**标记误报**
3. 可选备注（建议填写误报原因，如"CAM-03 右侧打光过强导致金属件反光"）
4. 点击提交

**审核后效果**：此聚类被标记为"误报"。系统自动生成一条知识条目（category=false_alarm），供应商后续可据此生成过滤规则。

---

#### 9.4.3 重命名（rename）

**什么时候用**：聚类默认名称为 `Cluster {id 前 8 位}`，不方便记忆和搜索。

**好的命名**：
- `CAM01_左前座椅_折痕_202605`
- `CAM03_右后靠背_反光误报`  
- `CAM02_头枕_划痕_批次A`

**差的命名**：
- `问题1`
- `缺陷`
- `111`

**操作步骤**：
1. 点击聚类的"审核"按钮
2. 选择操作类型：**重命名**
3. 输入新名称（建议格式：`相机编号_位置_缺陷类型_备注`）
4. 点击提交

---

#### 9.4.4 拆分（split）

**什么时候用**：某个聚类里混入了两种不同类型的异常，需要分开。

**典型场景**：
- AI 把 `CAM01` 的折痕和 `CAM02` 的污渍混到一个聚类里了
- 同一个相机拍到了两种不同位置的缺陷，被 AI 归为一组

**操作步骤**：
1. 打开聚类详情弹窗
2. 在成员列表中勾选需要移出的异常样本
3. 点击"审核"→ 选择 **拆分**
4. 系统自动创建新聚类（名称加 `_split` 后缀）
5. 可以对拆分后的两个聚类分别重命名和审核

**注意**：拆分后原聚类和新聚类的审核状态都会重置为"待审核"，需要分别再次审核。

---

#### 9.4.5 合并（merge）

**什么时候用**：两个或多个聚类实际是同一种缺陷/误报，AI 把它们分开了。

**典型场景**：
- 同一类划痕因为光照角度不同被 AI 分成了两个聚类
- 同一批次的污渍因为颜色深浅被 AI 分开了

**操作步骤**：
1. 打开要保留的那个聚类的详情
2. 点击"审核"→ 选择 **合并**
3. 在弹窗中勾选要合并进来的其他聚类（可多选）
4. 点击确认
5. 被合并的聚类会被删除，成员全部迁移到目标聚类

**注意事项**：
- 合并前确认两个聚类确实是同一类型
- 被合并的聚类会软删除（不可恢复），操作前仔细确认
- 建议先分别查看两个聚类的代表图像，确认无误后再合并

---

#### 9.4.6 忽略（ignore）

**什么时候用**：聚类样本量极少（只有 1~2 个）、图像质量太差看不清、或属于已知的无需关注的噪声。

**与"标记误报"的区别**：
- 标记误报 → 系统会学到"这类不是缺陷"，生成知识条目
- 忽略 → 系统不学任何东西，就当没见过这批数据

**什么时候选"忽略"而非"标记误报"**：当你不确定、或者样本太少不足以形成结论时，选"忽略"更安全。

### 9.5 审核质量控制

#### 9.5.1 好的审核

- 每个聚类至少查看 3 张以上代表图像再做判断
- 确认缺陷时选择了具体的缺陷类型
- 标记误报时备注了误报原因
- 遇到不确定的情况先"忽略"，不要强行判断

#### 9.5.2 坏的审核（请避免）

- 不查看图像直接批量通过
- 所有聚类都选同一个操作
- 不看 VLM 分析建议就直接否定
- 不确定的情况下胡乱选"确认缺陷"或"标记误报"

#### 9.5.3 不确定怎么办？

遵循以下优先级：
1. 先看 VLM 分析结论作为参考（AI 的判断有时很准）
2. 如果还是不确定 → 请教更资深的工艺同事
3. 如果依然无法判断 → 选择 **忽略**（宁可不学，不要学错）

> 原则：**宁可漏判一个，不要错判一个。** 一个错误的审核标签会误导后续的模型训练，比不审核的危害更大。

### 9.6 如何查看 VLM 辅助分析

每个聚类的详情弹窗中会展示 VLM（大模型）的自动分析结果：

| 字段 | 含义 | 如何使用 |
|------|------|----------|
| **anomaly_type** | VLM 判断的异常类型 | 与你的判断对比，如果一致说明 AI 判断准确 |
| **is_false_alarm** | VLM 是否认为是误报 | 重要参考——VLM 说误报而你觉得是缺陷时，多看几张图 |
| **reason** | VLM 的判定理由 | 了解 AI 的判断逻辑 |
| **confidence** | VLM 的置信度 (0~1) | < 0.5 时 AI 自己也不确定，需要你特别关注 |
| **suggestion** | VLM 的处理建议 | 参考建议，不一定要采纳 |

**重要提醒**：VLM 是辅助工具，不是最终裁判。**最终判断永远以你的结论为准。** 特别是 VLM confidence < 0.5 时，说明 AI 自身也没把握，这时候你的判断尤为重要。

### 9.7 常见缺陷类型速查手册

> 以下描述基于汽车座椅皮革/织物表面的常见场景，适用于绝大多数乘用车座椅。

| 缺陷类型 | 典型外观 | 易混淆为 | 区分要点 |
|----------|----------|----------|----------|
| **折痕** | 单条或多条平行压痕，方向与折叠/受力方向一致 | 划痕 | 折痕是**压出来的**（凹陷无破损），划痕是**划出来的**（表面可能有破损） |
| **划痕** | 不规则线状损伤，可能伴随表面材料破损起毛 | 折痕 | 划痕通常更窄更深，边缘不整齐，可能伴随颜色变化 |
| **反光（误报）** | 光滑表面（金属件/皮革）上的镜面高光区域 | 污渍 | 反光随视角变化位置会移动，污渍位置固定不动 |
| **污渍** | 不规则斑块或斑点，通常比周围区域颜色更深或更浅 | 反光 | 污渍从不同角度看都存在，反光只在一个角度出现 |
| **缝线偏移** | 缝线不直、缝线间距不均匀、跳针、断线 | 折痕 | 缝线偏移沿着缝合线分布，折痕不一定在缝线附近 |

### 9.8 日常检查清单

建议每天打开平台后按以下顺序操作：

| 检查项 | 位置 | 关注指标 |
|--------|------|----------|
| 1. 待审核聚类数 | Dashboard 统计卡片 | 是否持续增长（积压） |
| 2. 审核待办 | `/clusters` 筛选"待审核" | 每天至少清掉当天新增的待审核 |
| 3. 上次审核时间 | `/clusters` 表格列 | 确保不超过 3 天未审核 |
| 4. 误报率趋势 | Dashboard UMAP 图 | false_alarm 比例是否在下降 |
| 5. 异常上传量 | `/anomalies` 列表 | 是否有异常激增（可能线上出问题了） |

### 9.9 常见问题

**Q1：我有几天没审核了，积压了几十个聚类怎么办？**
A：按"VLM confidence"从高到低排审核——confidence 高的 AI 判断更可能正确，审核速度更快。不要试图全部审完，每天花 30 分钟即可。

**Q2：同一种缺陷被 AI 分成了好几个聚类怎么办？**
A：先用"合并"把它们合并成一个，然后再确认缺陷。比逐个确认效率更高。

**Q3：线上产线换了新的座椅型号，缺陷形态不一样了怎么办？**
A：这属于正常情况。按新形态继续审核即可，系统会自动学习新的缺陷模式。如果差异很大，可通知供应商评估是否需要调整模型。

**Q4：我审核错了可以改吗？**
A：当前版本审核记录不可撤销。如果审核错误，联系供应商工程师通过后台修正。后续版本会加入审核撤销功能。

**Q5：为什么需要我天天审核，不能让 AI 自己判断吗？**
A：AI 可以自动判断一部分（VLM 已经在做了），但 AI 的判断需要你的验证来纠偏。你审核的过程就是在教 AI"什么才是真正的缺陷"——没有这个过程，AI 的能力不会提升。你的目标是：随着时间推移，需要你审核的聚类越来越少（因为 AI 学会了）。

---

## 10. 在线检测核心 (seat_defect_core) 本地运行与测试指南

> **读者对象**：供应商工程师、开发人员和现场调试人员。本章覆盖 seat_defect_core（在线实时缺陷检测核心）的本地环境搭建、配置、运行和测试的完整流程。

### 10.1 组件说明

`seat_defect_core` 是在线实时检测核心程序，负责产线实时判定。它与离线分析平台的关系如下：

```
seat_defect_core (在线)                   离线分析平台 (本仓库)
═════════════════════                     ══════════════════
YOLO → ROI → PatchCore                  异常收集 → Embedding → 聚类
    → Filter Classifier                     → VLM 解释 → 人工审核
    → Rule Engine                          → 知识库 → 规则引擎
    → Fusion → OK/NG/REJECT               → 分类器训练 → 模型部署
         │                                      ↑          │
         └── NG 时自动上传异常 ──────────────────→          │
                                                           │
         模型自动加载 ←─── 部署桥接 ←──────────────────────┘
```

### 10.2 环境要求

| 项目 | 最低要求 | 推荐 |
|------|----------|------|
| Python | 3.11+ | 3.11 |
| 包管理器 | uv | uv |
| 操作系统 | macOS / Linux | macOS (Apple Silicon) / Linux (x86_64) |
| GPU | 不需要 | Apple MPS / NVIDIA CUDA |
| 磁盘空间 | ~5GB（含模型） | ~10GB |

### 10.3 首次安装

```bash
# 1. 进入 seat_defect_core 目录
cd seat_defect_core

# 2. 安装依赖（自动创建 .venv）
uv sync

# 3. 验证安装（从仓库根目录运行）
python -c "import sys; sys.path.insert(0, '.'); from seat_defect_core import SeatDefectInspector; print('OK')"
```

**注意**：所有命令从仓库根目录执行。`seat_defect_core/core_types/` 已重命名以避免与 Python 标准库 `types` 模块冲突。

### 10.4 目录结构与模型文件

```
offline-analysis-platform/
├── models/                              # 模型文件（需提前训练或从产线拷贝）
│   ├── yolo/
│   │   └── best.pt                      # YOLO 座椅检测模型 (ultralytics .pt)
│   └── seat_model_a/
│       ├── cam_0_lower_patchcore.npz    # 整 ROI PatchCore 模型
│       ├── cam_0_upper_patchcore.npz    # 区域 upper PatchCore 模型
│       └── cam_0_middle_patchcore.npz   # 区域 middle PatchCore 模型
├── deployed_models/                     # 部署桥接目标目录（后端自动写入）
│   └── line_a/
│       └── filter_classifier/
│           └── model.pt                 # 训练完成的 Filter Classifier
├── outputs/                             # 检测报告和调试产物
│   └── seat_defect_inspection/
│       ├── results.json                 # 最新检测报告
│       └── debug/                       # 调试产物目录
└── seat_defect_core/
    ├── config.example.json              # 检测配置文件（需按实际模型路径调整）
    └── pyproject.toml
```

### 10.5 配置文件说明

`config.example.json` 的关键字段：

| 字段路径 | 说明 | 示例值 |
|----------|------|--------|
| `part_id` | 工件编号 | `"seat_demo"` |
| `default_seat_model_id` | 默认座椅型号 | `"seat_model_a"` |
| `upload_base_url` | NG 自动上传目标 | `"http://localhost:8000"` |
| `fusion.ng_strategy` | 多机位融合策略 | `"any"` / `"all"` / `"majority"` |
| `cameras[].detection.model_path` | YOLO 模型路径 | `"../models/yolo/best.pt"` |
| `cameras[].patchcore_model_path` | PatchCore 模型路径 | `"../models/seat_model_a/cam_0_lower_patchcore.npz"` |
| `cameras[].patchcore.backbone_device` | 计算设备 | `"mps"` (Mac) / `"cpu"` / `"cuda:0"` |
| `cameras[].detection.device` | YOLO 设备 | `"mps"` (Mac) / `"cpu"` |
| `cameras[].filter_classifier.enabled` | 启用分类器 | `true` / `false`（无模型时关闭） |
| `cameras[].rule_engine.enabled` | 启用规则引擎 | `true` / `false` |
| `cameras[].regions[].box` | 区域归一化坐标 | `[x1, y1, x2, y2]` (0~1) |

所有路径字段相对于**配置文件所在目录**（即 `seat_defect_core/`）解析。

### 10.6 环境就绪检查（诊断工具）

运行诊断脚本，5 项检查确认环境是否就绪：

```bash
cd /path/to/offline-analysis-platform
./seat_defect_core/.venv/bin/python scripts/check_readiness.py
```

输出示例：

```
============================================================
  seat_defect_core 环境就绪检查
============================================================

[1] Python 版本
 [  OK  ] Python 3.11 (需要 >=3.11)

[2] Python 依赖
 [  OK  ] cv2 (opencv-python)
 [  OK  ] numpy (numpy)
 [  OK  ] torch (torch)
 [  OK  ] torchvision (torchvision)
 [  OK  ] ultralytics (ultralytics)
 [  OK  ] requests (requests)

[3] 加速设备
 [  OK  ] torch 2.12.0 — CPU=True, MPS=True, CUDA=False

[4] 检测配置
 [  OK  ] 配置加载成功

[5] 模型文件检查
 [  OK  ] cam_front (整ROI): .../cam_0_lower_patchcore.npz
 [  OK  ] cam_front/upper: .../cam_0_upper_patchcore.npz
 [  OK  ] cam_front/middle: .../cam_0_middle_patchcore.npz
 [  OK  ] YOLO: .../models/yolo/best.pt
```

### 10.7 准备测试图片

将产线采集的座椅图片放入 `sample_images/` 目录，文件名格式为 `{camera_id}.jpg`：

```
sample_images/
├── cam_front.jpg      ← 正面机位图片
├── cam_side.jpg       ← 侧面机位图片（如有）
└── ...
```

文件名（不含扩展名）会自动映射为 `camera_id`，与配置文件中定义的机位 ID 对应。

### 10.8 运行单次检测

```bash
# 基本用法
./seat_defect_core/.venv/bin/python -m seat_defect_core \
  --config seat_defect_core/config.example.json \
  --images "cam_front=sample_images/cam_front.jpg" \
  --part-id test_001

# 带所有参数
./seat_defect_core/.venv/bin/python -m seat_defect_core \
  --config seat_defect_core/config.example.json \
  --images "cam_front=sample_images/cam_front.jpg" \
  --part-id part_20260522_001 \
  --seat-model-id seat_model_a \
  --upload http://localhost:8000 \
  --output outputs/test_result.json

# 预热模式（预加载模型，后续检测更快）
./seat_defect_core/.venv/bin/python -m seat_defect_core \
  --config seat_defect_core/config.example.json \
  --images "cam_front=sample_images/cam_front.jpg" \
  --warmup
```

### 10.9 通过 Python API 调用

```python
import sys
sys.path.insert(0, "/path/to/offline-analysis-platform")

from seat_defect_core import SeatDefectInspector

inspector = SeatDefectInspector("seat_defect_core/config.example.json")

# 方式 1：从图片路径检测
response, camera_images = inspector.inspect_paths(
    {"cam_front": "sample_images/cam_front.jpg"},
    part_id="test_001",
    seat_model_id="seat_model_a",
)
print(f"status: {response.status}")
print(f"reason: {response.decision_reason}")

# 方式 2：从 numpy 数组检测
import cv2
img = cv2.imread("sample_images/cam_front.jpg")
response, camera_images = inspector.inspect(
    [{"camera_id": "cam_front", "image": img}],
    part_id="test_001",
)
```

### 10.10 理解检测结果

检测报告自动写入 `outputs/seat_defect_inspection/results.json`：

```json
{
  "status": "NG",
  "decision_reason": "ng_from_cam_front",
  "camera_results": [{
    "camera_id": "cam_front",
    "status": "NG",
    "reason": "region_texture_anomaly:upper,middle",
    "quality": {"accepted": true, "metrics": {...}},
    "region_results": [{
      "region_id": "upper",
      "status": "NG",
      "texture_result": {
        "score": 152.5,
        "threshold": 88.8,
        "is_anomaly": true,
        "strong_patch_count": 46
      }
    }]
  }]
}
```

**状态含义**：

| status | 含义 | 后续动作 |
|--------|------|----------|
| `OK` | 检测通过，未发现异常 | 放行 |
| `NG` | 检测到缺陷 | 隔离 + 上传离线平台 |
| `REJECT` | 检测条件不满足 | 检查图像质量/ROI/配置 |

**常见 reason**：

| reason | 说明 |
|--------|------|
| `texture_anomaly` | 完整 ROI PatchCore 判定为纹理异常 |
| `region_texture_anomaly:<ids>` | 区域 PatchCore 判定异常 |
| `filter_classifier_suppressed` | 分类器抑制了 PatchCore 误报 |
| `target_not_found` | YOLO 未检测到目标座椅 |
| `low_valid_patch_ratio` | 有效 patch 比例不足 |
| `quality_<reason>` | 图像质量不合格 |

### 10.11 端到端联动测试（在线检测 + 离线平台）

验证完整数据闭环——从在线检测到离线分析平台的全链路。

#### 前置条件

```bash
# 1. 启动离线平台后端
cd backend && docker compose up -d

# 2. 确认所有服务健康
docker compose ps
curl http://localhost:8000/health

# 3. 准备测试图片（放入 sample_images/ 目录）
#    文件命名格式: {camera_id}.jpg
#    例如: cam_front.jpg, cam_side.jpg
mkdir -p sample_images
# 将产线采集的座椅图片复制到此目录
```

#### 运行端到端 Demo

```bash
# 完整闭环模式（需要后端运行 + 已放置测试图片）
cd /path/to/offline-analysis-platform
./seat_defect_core/.venv/bin/python scripts/demo_full_loop.py \
  --backend http://localhost:8000 \
  --images ./sample_images

# 纯检测模式（不需要后端）
./seat_defect_core/.venv/bin/python scripts/demo_full_loop.py \
  --images ./sample_images \
  --no-upload
```

Demo 自动执行 5 个步骤：
1. 检查后端健康状态
2. 从 `--images` 目录发现测试图片（按文件名匹配 camera_id）
3. 加载检测配置
4. 运行 seat_defect_core 检测
5. 将 NG 结果上传到离线平台

#### 手动触发离线分析

NG 异常上传到后端后，可以手动触发离线分析管线：

```bash
# 触发聚类分析（处理所有 pending 状态异常）
curl -X POST http://localhost:8000/api/cluster/trigger \
  -H "Content-Type: application/json" \
  -d '{"min_cluster_size": 5, "min_samples": 3}'

# 查询异常列表确认上传成功
curl "http://localhost:8000/api/anomaly/list?status=pending"
```

### 10.12 常见问题排查

**Q1：运行检测时提示 `ModuleNotFoundError: No module named 'cv2'`**

A：依赖未安装。运行 `cd seat_defect_core && uv sync`。

**Q2：提示 `ModuleNotFoundError: No module named 'seat_defect_core'`**

A：确保从仓库根目录运行命令，且 `seat_defect_core/` 目录存在于当前路径下。

**Q3：提示 `target_not_found`**

A：YOLO 模型未检测到座椅。检查：
- `detection.model_path` 是否正确指向有效的 YOLO .pt 文件
- 图片中是否确实有座椅
- `detection.confidence` 是否设置过高

**Q4：提示 `low_valid_patch_ratio`**

A：有效 patch 比例不足。检查：
- `patchcore.min_target_coverage` 是否设置过高
- `roi.mask_erode_pixels` 是否腐蚀过多
- ROI 对齐参数是否与训练时一致

**Q5：检测速度慢（首次 > 60s）**

A：首次运行需要：
- 下载 torchvision 预训练 backbone 权重（~200MB，仅一次）
- JIT 编译 YOLO 模型
后续运行会显著加快（缓存命中）。

**Q6：Mac 上 MPS 加速不生效**

A：确认 `backbone_device` 和 `detection.device` 都设为 `"mps"`。如果遇到 MPS 相关报错，回退为 `"cpu"`。

**Q7：如何临时关闭某个模块进行测试**

A：在配置文件中设置对应 `enabled` 字段为 `false`：
- `filter_classifier.enabled: false` — 跳过分类器（无模型时）
- `rule_engine.enabled: false` — 跳过规则引擎
- `color_branch.enabled: false` — 跳过颜色分支
- `cameras[].enabled: false` — 跳过某个机位
- `regions[].enabled: false` — 跳过某个区域

**Q8：如何验证部署的 Filter Classifier 模型已生效**

A：运行检测后查看输出中的 `filter_result` 字段：
```bash
cat outputs/seat_defect_inspection/results.json | python3 -c "
import json, sys
d = json.load(sys.stdin)
for cam in d['camera_results']:
    fr = cam.get('filter_result')
    if fr:
        print(f'classifier: is_real_defect={fr[\"is_real_defect\"]} confidence={fr[\"confidence\"]:.3f}')
    else:
        print('classifier: 未执行（enabled=false 或模型未就绪）')
"
```
