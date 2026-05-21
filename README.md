 <h1 align="center">🏭 Industrial AI Offline Analysis Platform</h1>

<h3 align="center">工业座椅缺陷检测 — 离线智能分析平台</h3>

<p align="center">
  <b>AI 智能进化平台</b> · 持续学习，持续优化，持续降低误报率
</p>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python"></a>
  <a href="https://fastapi.tiangolo.com/"><img src="https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI"></a>
  <a href="https://react.dev/"><img src="https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black" alt="React"></a>
  <a href="https://www.postgresql.org/"><img src="https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL"></a>
  <a href="https://www.docker.com/"><img src="https://img.shields.io/badge/Docker-✓-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow?style=flat-square" alt="License"></a>
</p>

<p align="center">
  <b>171+ 源文件</b> · <b>32 个 API 端点</b> · <b>8 个 Celery Worker</b> · <b>8 个前端页面</b> · <b>9 个 ML 模块</b> · <b>6 个 Docker 服务</b>
</p>

---

## 项目简介

一个面向工业座椅缺陷检测的**闭环 AI 进化平台**。本系统**离线运行**，持续积累产线异常样本，通过 Embedding 提取、无监督聚类、多模态大模型解释、人工复核、知识库构建、规则引擎和分类器训练，最终将优化后的模型反哺至在线检测系统，形成持续降低误报率的数据飞轮。

> [!IMPORTANT]
> 本系统**不参与在线实时检测**。定位为离线"大脑"——负责学习、归纳、进化，在线系统负责毫秒级实时决策。

---

## 系统架构

```mermaid
flowchart TB
    subgraph ONLINE["🔴 在线检测系统"]
        direction LR
        CAM["📷 相机输入"] --> YOLO["YOLO<br/>ROI 检测"]
        YOLO --> PC["PatchCore<br/>异常评分"]
        PC --> FC["Filter<br/>分类器"]
        FC --> DECISION{"OK / NG"}
    end

    subgraph OFFLINE["🔵 离线分析平台（本仓库）"]
        direction TB
        INGEST["📥 异常样本<br/>收集缓冲"] --> EMBED["🧬 Embedding<br/>ResNet18 · 512维"]
        EMBED --> CLUSTER["🔬 聚类分析<br/>UMAP + HDBSCAN"]
        CLUSTER --> VLM["🤖 多模态解释<br/>Qwen2.5-VL"]
        VLM --> REVIEW["👨‍🔧 人工复核<br/>确认/误报/拆分/合并"]
        REVIEW --> KB["📚 知识库<br/>缺陷模式沉淀"]
        REVIEW --> RULES["🧠 规则引擎<br/>优先级评估"]
        KB --> TRAIN["🎯 分类器训练<br/>MobileNetV3"]
        TRAIN --> REGISTRY["📦 模型注册<br/>MLflow"]
    end

    ONLINE -->|"异常样本"| INGEST
    REGISTRY -->|"部署优化模型"| FC
```

---

## 核心功能

<table>
  <tr>
    <td width="50%">
      <h3>🧬 Embedding 提取与相似检索</h3>
      <ul>
        <li>ResNet18 骨干网络，ImageNet 预训练</li>
        <li>512 维特征向量，存入 <b>pgvector</b>（IVFFlat 索引）</li>
        <li>支持按异常 ID 或原始向量进行余弦相似度检索</li>
        <li>Celery 异步批量提取，不阻塞 API</li>
        <li>Grad-CAM 热力图生成 + Pillow 缩略图生成</li>
      </ul>
    </td>
    <td width="50%">
      <h3>🔬 无监督聚类发现</h3>
      <ul>
        <li>StandardScaler → UMAP → HDBSCAN 完整 Pipeline</li>
        <li>无需人工标注，自动发现缺陷模式</li>
        <li>每个簇自动选取代表样本</li>
        <li>Celery Beat 每 <b>6 小时</b>自动触发完整离线分析周期 (Pipeline 编排)</li>
      </ul>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <h3>🤖 多模态 VLM 异常解释</h3>
      <ul>
        <li>Qwen2.5-VL / InternVL，通过 vLLM 端点推理</li>
        <li>同时分析原图、ROI、热力图、裁剪图</li>
        <li>结构化 JSON 输出：缺陷类型、误报判断、原因分析、置信度</li>
      </ul>
    </td>
    <td width="50%">
      <h3>👨‍🔧 人工复核工作流</h3>
      <ul>
        <li>6 种操作：确认缺陷 / 标记误报 / 重命名 / 拆分 / 合并 / 忽略</li>
        <li>复核后自动生成知识库条目</li>
        <li>完整审计追溯：复核人 + 时间戳 + 状态变更</li>
      </ul>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <h3>📚 知识库 + 规则引擎</h3>
      <ul>
        <li>缺陷模式库：分类、相机关联、建议动作（忽略 / NG / 复核）</li>
        <li>优先级规则引擎，支持在线过滤</li>
        <li>一键从知识条目生成规则</li>
        <li>内置评估模拟器，测试规则命中效果</li>
      </ul>
    </td>
    <td width="50%">
      <h3>🎯 分类器训练与模型部署</h3>
      <ul>
        <li>支持 MobileNetV3 / EfficientNet / ResNet18</li>
        <li>Adam + ReduceLROnPlateau + Early Stopping (patience=10)</li>
        <li>自动数据加载：从 MinIO 读取已审核聚类数据，train/val split</li>
        <li>导出 TorchScript / ONNX，自动注册至 <b>MLflow</b> 和数据库</li>
        <li>安全部署 + 版本化回滚</li>
      </ul>
    </td>
  </tr>
</table>

---

## 技术栈

<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/SQLAlchemy-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white" alt="SQLAlchemy">
  <img src="https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white" alt="Redis">
  <img src="https://img.shields.io/badge/Celery-37814A?style=for-the-badge&logo=celery&logoColor=white" alt="Celery">
  <img src="https://img.shields.io/badge/MinIO-C72E49?style=for-the-badge&logo=minio&logoColor=white" alt="MinIO">
  <br>
  <img src="https://img.shields.io/badge/PyTorch-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white" alt="PyTorch">
  <img src="https://img.shields.io/badge/MLflow-0194E2?style=for-the-badge&logo=mlflow&logoColor=white" alt="MLflow">
  <img src="https://img.shields.io/badge/React-61DAFB?style=for-the-badge&logo=react&logoColor=black" alt="React">
  <img src="https://img.shields.io/badge/Ant_Design-0170FE?style=for-the-badge&logo=ant-design&logoColor=white" alt="Ant Design">
  <img src="https://img.shields.io/badge/Plotly-3F4F75?style=for-the-badge&logo=plotly&logoColor=white" alt="Plotly">
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker">
</p>

---

## 项目结构

```
offline-analysis-platform/
├── backend/                          # Python 后端（125+ 文件）
│   ├── app/
│   │   ├── api/                      # 9 个 FastAPI 路由，32 个端点
│   │   │   ├── anomaly/              #   上传 · 列表 · 详情 · 重新处理
│   │   │   ├── cluster/              #   列表 · 详情 · 可视化 · 触发聚类
│   │   │   ├── review/               #   提交复核 · 查询历史
│   │   │   ├── embedding/            #   按异常 ID / 向量相似检索
│   │   │   ├── knowledge/            #   增删改查 · 全文搜索 · 按簇查询
│   │   │   ├── rules/                #   增删改查 · 在线评估 · 开关 · 从知识库生成
│   │   │   ├── training/             #   启动训练 · 查询状态 · 模型列表
│   │   │   └── registry/             #   部署 · 回滚 · 部署历史
│   │   ├── domain/                   # 6 个领域模型 + Protocol 接口
│   │   ├── services/                 # 8 个业务服务模块
│   │   ├── repositories/             # 5 个 Repository（封装所有 DB 访问）
│   │   ├── models/                   # 9 个 SQLAlchemy ORM 表（含 pgvector）
│   │   ├── schemas/                  # Pydantic v2 请求/响应 Schema
│   │   ├── workers/                  # 8 个 Celery Worker 模块（含 Pipeline 编排）
│   │   ├── infrastructure/           # 数据库 · MinIO · pgvector · Celery · 配置
│   │   ├── core/                     # 配置类 · 异常体系 · 安全工具
│   │   ├── common/                   # 共享类型 · structlog 结构化日志
│   │   └── tests/                    # pytest-asyncio（6 个测试套件）
│   ├── alembic/                      # 数据库迁移脚本
│   ├── docker-compose.yml            # 6 服务编排
│   ├── Dockerfile                    # API 镜像
│   ├── Dockerfile.worker             # GPU Worker 镜像
│   └── pyproject.toml                # 依赖与工具配置
├── frontend/                         # React 前端（33+ 源文件）
│   ├── index.html                    # Vite 入口 HTML
│   ├── vite.config.ts                # Vite 配置 + API 代理
│   ├── tailwind.config.js            # TailwindCSS 配置
│   └── src/
│       ├── app/                      # layout.tsx · router.tsx（React Router）
│       ├── features/                 # 功能页面（Feature-based 架构）
│       │   ├── dashboard/            #   看板：UMAP 散点图 · 复核柱状图 · 统计卡片
│       │   ├── cluster-review/       #   聚类复核：列表 · 详情弹窗 · 复核弹窗
│       │   ├── anomaly-browser/      #   异常浏览：筛选 · 列表 · 详情 · 相似检索
│       │   ├── anomaly-upload/       #   异常上传：JSON元数据 · multipart文件上传
│       │   ├── knowledge-base/       #   知识库：增删改查 · 全文搜索 · 创建表单
│       │   ├── rules-engine/         #   规则引擎：启停开关 · 评估模拟器 · 创建表单
│       │   ├── training/             #   训练管理：模型列表 · 启动训练 · 状态轮询
│       │   └── model-deploy/         #   模型部署：部署历史 · 部署操作 · 回滚确认
│       ├── api/                      # Axios API 客户端（按 domain 拆分）
│       ├── types/                    # TypeScript 类型定义（按 domain 拆分）
│       ├── hooks/                    # useApi 通用 hook
│       ├── components/ui/            # PageHeader 等共享 UI 组件
│       └── lib/                      # constants 等共享常量
└── ml/                               # ML 模块（9 文件）
    ├── embedding/                    # ResNet18 提取器（512 维）
    ├── clustering/                   # UMAP + HDBSCAN Pipeline
    ├── classifier/                   # MobileNetV3 训练器 + ONNX 导出
    └── vlm/                          # Qwen2.5-VL 多模态分析器
```

---

## 快速开始

### 环境要求

- **Docker** & **Docker Compose**
- **Python 3.11+**（本地开发）
- **NVIDIA GPU**（可选，用于 ML Worker）

### Docker Compose 一键启动（推荐）

```bash
cd backend
cp .env.example .env
docker compose up -d
```

<details>
<summary><b>启动 6 个服务</b></summary>

| 服务 | 端口 | 说明 |
|---|---|---|
| **API** | `8000` | FastAPI 接口 + Swagger 文档 |
| **Worker** | — | Celery GPU Worker（ML 任务） |
| **PostgreSQL** | `5432` | pgvector `IVFFlat` 向量索引 |
| **Redis** | `6379` | 消息队列 + 结果后端 |
| **MinIO** | `9000` / `9001` | 对象存储 + Web 控制台 |
| **MLflow** | `5000` | 模型注册与实验追踪 |

</details>

```bash
# 健康检查
curl http://localhost:8000/health
# → { "status": "healthy", "version": "0.1.0" }

# API 文档
open http://localhost:8000/docs       # Swagger UI
open http://localhost:8000/redoc      # ReDoc
```

### 本地开发

```bash
# 安装 uv（如果尚未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 后端
cd backend
uv sync                             # 自动创建 .venv + 安装所有依赖
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000

# 前端
cd frontend
pnpm install && pnpm run dev          # → http://localhost:3000

# Celery Worker
cd backend
uv run celery -A app.infrastructure.queue.celery_app worker -l info -c 4
```

---

## API 总览

> 所有端点文档详见 **[`/docs`](http://localhost:8000/docs)**（Swagger）和 **[`/redoc`](http://localhost:8000/redoc)**

```
                     POST   /api/anomaly/upload                    📥 上传异常
                     POST   /api/anomaly/upload-with-files         (multipart 文件上传)
                     GET    /api/anomaly/list · /{id}
                     POST   /api/anomaly/{id}/reprocess

                     GET    /api/cluster/list · /{id}              🔬 聚类分析
                     GET    /api/cluster/visualization
                     POST   /api/cluster/trigger

                     POST   /api/cluster/review                    ✏️  人工复核
                     GET    /api/cluster/{id}/reviews

                     GET    /api/embedding/search                  🔍 向量检索
                     POST   /api/embedding/search

                     CRUD   /api/knowledge/entries                 📚 知识库
                     GET    /api/knowledge/entries/search
                     GET    /api/knowledge/clusters/{id}/entries

                     CRUD   /api/rules                             🧠 规则引擎
                     POST   /api/rules/evaluate
                     POST   /api/rules/{id}/toggle
                     POST   /api/rules/generate-from-knowledge

                     POST   /api/training/start                    🎯 模型训练
                     GET    /api/training/status/{task_id}

                     POST   /api/model/deploy                      📦 模型部署
                     POST   /api/model/deploy/{target}/rollback

                     POST   /api/multimodal/analyze/cluster/{id}    🤖 多模态分析
                     POST   /api/multimodal/analyze/batch
                     POST   /api/multimodal/analyze/anomaly/{id}
```

---

## 前端页面

| 页面 | 路由 | 功能说明 |
|:---|:---:|---|
| **Dashboard** | `/` | Plotly UMAP 散点图 · 复核状态分布柱状图 · 4 个统计指标卡片 |
| **Cluster Review** | `/clusters` | 聚类列表筛选 · 详情弹窗（代表图 + 成员列表） · 一键复核 |
| **Anomaly Browser** | `/anomalies` | 相机/状态筛选 · PhotoView 图片浏览（缩放/旋转） · 相似检索 · 重新处理 |
| **Anomaly Upload** | `/upload` | JSON 元数据提交 · multipart 文件上传（原图/ROI/热力图/裁剪图） |
| **Knowledge Base** | `/knowledge` | 条目增删改查 · 全文搜索 · 按分类/缺陷类型筛选 · 一键生成规则 |
| **Rules Engine** | `/rules` | 规则增删改查 · 启停开关 · 在线评估模拟器 · 从知识库生成规则 |
| **Training** | `/training` | 模型列表 · 架构/超参配置启动训练 · 状态轮询（5s） |
| **Model Deploy** | `/deploy` | 部署历史一览 · 选择模型/版本/目标部署 · 在线模型安全回滚 |

---

## 设计原则

<p>
  <img src="https://img.shields.io/badge/API_→_Service_→_Domain_→_Repository_→_Infrastructure-分层架构-blue?style=flat-square" alt="分层">
  <img src="https://img.shields.io/badge/Protocol_AI_接口-模型可替换-green?style=flat-square" alt="Protocol">
  <img src="https://img.shields.io/badge/全链路异步-非阻塞-red?style=flat-square" alt="Async">
  <img src="https://img.shields.io/badge/Repository_模式-可测试-orange?style=flat-square" alt="Repository">
  <img src="https://img.shields.io/badge/Pydantic_Settings-零硬编码-purple?style=flat-square" alt="Settings">
  <img src="https://img.shields.io/badge/structlog-结构化日志-gray?style=flat-square" alt="Logging">
</p>

| 原则 | 实践 |
|---|---|
| **严格分层架构** | API 层只处理 HTTP，零数据库访问、零业务逻辑 |
| **Protocol 接口抽象** | `EmbeddingExtractor` 和 `VLMAnalyzer` 采用 Protocol 定义，替换模型无需改动业务代码 |
| **全链路异步** | Async FastAPI + async SQLAlchemy + async MinIO，CPU/GPU 密集型任务全部交 Celery Worker 异步执行 |
| **Repository 模式** | 所有 DB 访问封装在类型安全的 Repository 中，测试可直接用 SQLite 内存库替代 |
| **零硬编码** | Pydantic Settings 从环境变量读取所有配置，禁止 `DB_HOST = "localhost"` |
| **结构化日志** | structlog 输出 JSON 行日志，绑定 `trace_id` `cluster_id` `anomaly_id` `model_version` `camera_id` 上下文 |

---

## 环境变量

完整列表见 [`backend/.env.example`](backend/.env.example)。

| 变量 | 默认值 |
|---|---|
| `POSTGRES_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/anomaly_db` |
| `REDIS_URL` | `redis://localhost:6379/0` |
| `MINIO_ENDPOINT` | `localhost:9000` |
| `VLM_ENDPOINT` | `http://localhost:8888/v1` |
| `MLFLOW_TRACKING_URI` | `http://localhost:5000` |
| `EMBEDDING_DIM` | `512` |
| `CLUSTERING_MIN_SIZE` | `10` |
| `DEBUG` | `false` |

---

## 测试

```bash
cd backend
uv run pytest -v                                  # 全部 26 个测试用例
uv run pytest app/tests/ -v --cov=app             # 含覆盖率报告
uv run pytest app/tests/test_rule_engine.py -v    # 单独文件
```

| 测试套件 | 覆盖内容 |
|---|---|
| `test_exceptions` | 全部 10 种异常类型及其错误码 |
| `test_anomaly_repository` | 创建、按ID查询、更新状态、不存在记录 |
| `test_clustering_service` | 默认配置、自定义配置 |
| `test_knowledge_service` | 创建条目、从复核自动生成、搜索 |
| `test_rule_engine` | CRUD、优先级评估、启停开关、相机过滤 |
| `test_api` | 健康检查、空列表、资源不存在、无结果搜索 |

---

## 参与贡献

欢迎提交 Issue 和 Pull Request。开发环境使用 [uv](https://docs.astral.sh/uv/) 管理 Python 依赖：

```bash
uv sync          # 安装依赖
uv run pytest    # 运行测试
uv run mypy app  # 类型检查
uv run ruff check app  # 代码检查
```

请遵循项目代码规范：

- 每个 Python 文件首行 `from __future__ import annotations`
- 完整类型注解（mypy strict 兼容）
- 函数 < 50 行，类 < 300 行
- 禁止 `utils.py` 杂物堆
- 所有 DB 访问走 Repository
- 所有 Schema 继承 Pydantic v2 `BaseModel`
- 所有日志使用 structlog

---

## 许可证

[MIT](LICENSE)

---

<p align="center">
  <sub>为工业 AI 而生 — 持续学习，持续进化。</sub>
</p>
