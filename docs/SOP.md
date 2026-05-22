# 离线分析平台 — 标准操作流程 (SOP)

## 1. 系统概述

本平台是一个 **工业 AI 离线智能分析平台**，面向汽车座椅缺陷检测场景。它与线上实时检测系统（YOLO + PatchCore + Filter Classifier）配合运行，但**自身不参与线上实时判定**，而是作为"AI 进化大脑"持续学习线上采集的异常样本，通过聚类分析、VLM 解释、人工审核、知识沉淀和模型训练，反哺线上系统以**持续降低误报率**。

### 1.1 核心业务流程

```
线上检测系统 → 异常样本上传 → 特征提取(ResNet18) → 无监督聚类(UMAP+HDBSCAN)
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
| ML | PyTorch, ResNet18, UMAP, HDBSCAN, Qwen2.5-VL/InternVL |

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
   - **Anomaly Score**: 异常分数 (0.0~1.0)
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
| 特征提取 | MinIO 中的 crop 图像 | ResNet18 → 512 维向量 | pgvector 存储的 EmbeddingVector |
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
| ResNet18 | 与嵌入提取使用相同架构 |

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
| `INDUSTRIAL_EMBEDDING_MODEL` | `resnet18` | 嵌入模型 |
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
