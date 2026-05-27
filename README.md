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
  <b>370+ 源文件</b> · <b>65+ API 端点</b> · <b>14 个 Celery Worker</b> · <b>8 个前端页面</b> · <b>11 个 ML 模块</b> · <b>6 个 Docker 服务</b> · <b>70+ 个测试</b>
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
    subgraph ONLINE["🔴 在线检测系统 (seat_defect_core)"]
        direction LR
        CAM["📷 相机输入"] --> YOLO["YOLO<br/>ROI 检测"]
        YOLO --> PC["EfficientAD<br/>异常评分 + 特征提取"]
        PC --> CAL["Feature Calibration<br/>Normalize→Project→Whiten"]
        CAL --> BC["Cascading Budget<br/>Proposal+Filter 级联预算"]
        BC --> RP["Region Proposal<br/>热力图→连通域→裁剪"]
        RP --> IL["Identity Linking<br/>Kalman+特征匹配"]
        RP --> FC["Three-Modal Filter<br/>图像+EAD+Unified Emb 三模态"]
        FC --> AG["Proposal Aggregation<br/>加权聚合判定"]
        AG --> RE["规则引擎<br/>后处理"]
        RE --> DECISION{"OK / NG"}
    end

    subgraph OFFLINE["🔵 离线分析平台（本仓库）"]
        direction TB
        INGEST["📥 异常样本<br/>收集缓冲"] --> ISOLATION["🔒 数据隔离<br/>seat_model+camera+region"]
        ISOLATION --> MASK["🧹 Mask Refinement<br/>背景消除/标准化"]
        MASK --> DUAL["🔀 双轨对比<br/>Raw vs Refined Embedding"]
        DUAL --> EMBED["🧬 Embedding<br/>DINOv2-S · 384维"]
        EMBED --> CLUSTER["🔬 聚类分析<br/>UMAP + HDBSCAN"]
        CLUSTER --> GRAPH["🕸 相似度图谱<br/>KNN Graph Builder"]
        CLUSTER --> VLM["🤖 多模态解释<br/>Qwen2.5-VL"]
        VLM --> REVIEW["👨‍🔧 人工复核<br/>确认/误报/拆分/合并"]
        REVIEW --> KB["📚 知识库<br/>缺陷模式沉淀"]
        REVIEW --> RULES["🧠 规则引擎<br/>优先级评估"]
        REVIEW --> TAX["🌳 缺陷分类树<br/>层级缺陷分类"]
        KB --> TRAIN["🎯 分类器训练<br/>MobileNetV3"]
        KB --> METRIC["📐 度量学习<br/>ArcFace / Triplet Loss"]
        TRAIN --> GATE["🛡 模型门禁<br/>召回率/抑制率/分层评估"]
        METRIC --> GATE
        GATE --> REGISTRY["📦 模型注册<br/>MLflow"]
        REGISTRY --> DEPLOY["🚀 原子部署<br/>模型 + 规则"]
        DEPLOY --> HOT["🔴 在线热重载<br/>Canary · Checksum · 回滚"]
    end

    ONLINE -->|"NG 自动上传<br/>PatchProposal + Features"| INGEST
    HOT -->|"reload.signal<br/>三模态 Filter + Projector 热重载"| AP
```

---

## 核心功能

<table>
  <tr>
    <td width="50%">
      <h3>🧬 Embedding 提取与相似检索</h3>
      <ul>
        <li>DINOv2-S 自监督视觉大模型，像素级密集特征</li>
        <li>384 维特征向量，存入 <b>pgvector</b>（IVFFlat 索引）</li>
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
        <li>支持 MobileNetV3 / EfficientNet / ResNet18 + ArcFace / Triplet Loss 度量学习</li>
        <li>Adam + ReduceLROnPlateau + Early Stopping (patience=10)</li>
        <li>自动数据加载：从 MinIO 读取已审核聚类数据，train/val split</li>
        <li>按 defect_type 自动分组构建度量学习多类训练数据</li>
        <li>导出 TorchScript / ONNX，自动注册至 <b>MLflow</b> 和数据库</li>
        <li>安全部署 + 版本化回滚 + 🔴 热重载信号自动通知在线系统</li>
      </ul>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <h3>🔄 在线检测核心 (seat_defect_core)</h3>
      <ul>
        <li>完整在线推理 pipeline：YOLO → ROI → EfficientAD(<b>特征提取</b>) → <b>Feature Calibration</b> → <b>Cascading Budget</b> → <b>Region Proposal</b> → <b>Identity Linking</b> → <b>Three-Modal Filter</b> → <b>Aggregation</b> → <b>Rule Engine</b> → Fusion</li>
        <li><b>Patch-level Feature Harvesting</b>：Forward Hook 捕获 EfficientAD Teacher 多层特征 + Student-Teacher 差异，保留 anomaly representation 而非仅 score</li>
        <li><b>Feature Calibration Layer</b>：CameraNormalizer (机位级 per-channel 标准化) → EmbeddingProjector (多尺度特征 → PCA 投影至 384-dim) → WhiteningTransform (ZCA 白化去相关) → EMAFeatureCenter (缺陷类型特征中心 EMA 追踪)，跨机位统一特征空间</li>
        <li><b>Region Proposal Refinement</b>：热力图 → 自适应阈值 → 形态学清理 → 连通域 → 区域裁剪，每个 defect patch 独立送入 Filter</li>
        <li><b>Three-Modal Filter</b>：MobileNetV3-Small (448²) 图像分支 + EfficientAD 特征分支 + Unified Embedding (384d) → 768d Fusion → 二分类，Feature Dropout 保证 fallback</li>
        <li><b>Cascading Budget Controller</b>：两级预算（Proposal + Filter 级联），自适应阈值 + 动态 per-patch 过滤调度 (full/partial/skip_all/emergency)，延迟 SLA 保证 (target 15ms / hard 20ms)</li>
        <li><b>Identity Linking</b>：6态生命周期 + Kalman/特征余弦级联匹配 + 4类冲突解决策略，跨帧去重，跨相机关联</li>
        <li><b>Proposal Aggregation</b>：加权聚合 (area^0.5 × score)，Generation 优化 Recall，Aggregation 优化 Precision</li>
        <li>故障安全：推理失败默认 is_real_defect=True，不拦截真实缺陷</li>
        <li>规则引擎后处理：可配置阈值规则，支持 suppress_to_ok / flag_for_review</li>
        <li>全 ROI 单模型 EfficientAD + Proposal + Filter 级联判定</li>
      </ul>
    </td>
    <td width="50%">
      <h3>🌳 缺陷分类树</h3>
      <ul>
        <li>4 大类预设分类体系：表面缺陷 / 缝线缺陷 / 结构缺陷 / 光学异常</li>
        <li>自引用层级结构（parent_id），支持多级细分</li>
        <li>审核确认缺陷时自动关联分类树节点</li>
        <li>树统计 API：各节点下的异常计数和聚类计数</li>
        <li>支持自定义扩展和人工调整分类结构</li>
      </ul>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <h3>🕸 相似度图谱</h3>
      <ul>
        <li>基于 pgvector 的 KNN 图谱构建</li>
        <li>预计算相似边，支持快速邻居查询</li>
        <li>BFS 最短路径导航（max_hops 可配置）</li>
        <li>以任意异常为中心的子图探索</li>
        <li>图谱构建记录追踪 + Celery 异步重建</li>
      </ul>
    </td>
    <td width="50%">
      <h3>📐 度量学习训练</h3>
      <ul>
        <li>ArcFace 加性角度边际损失：同类嵌入更紧凑</li>
        <li>Triplet Loss：锚点/正样本/负样本三元组优化</li>
        <li>EmbeddingBackbone：从 MobileNetV3/ResNet/EfficientNet 提取归一化嵌入</li>
        <li>按 defect_type 自动分组构建多类训练数据</li>
        <li>训练完成后自动导出 TorchScript + 注册 MLflow</li>
      </ul>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <h3>🧹 Mask Refinement + 双轨对比</h3>
      <ul>
        <li>GrabCut 前景/背景分离，去除背景噪声</li>
        <li>CLAHE 自适应直方图均衡化，标准化光照</li>
        <li>形态学操作：闭运算填充孔洞 + 开运算去噪</li>
        <li><b>双轨 Embedding 对比</b>：Raw vs Refined 聚类质量评估</li>
        <li>自动推荐最优精化策略，Celery 批量处理</li>
      </ul>
    </td>
    <td width="50%">
      <h3>🔴 在线热重载</h3>
      <ul>
        <li>reload.signal 信号文件机制，在线系统自动检测模型更新</li>
        <li>A/B 模型版本管理（Active / Shadow），支持 Canary 灰度提升</li>
        <li><b>SHA256 Checksum 校验</b>：部署前后完整性验证</li>
        <li><b>回滚版本绑定</b>：manifest.json 追踪切换历史 + 安全回滚</li>
        <li><b>训练完成自动 Canary 部署</b>：仅部署至 Shadow，通过后手动 Promote</li>
      </ul>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <h3>🔒 数据隔离</h3>
      <ul>
        <li><b>三级隔离键</b>：seat_model_id + camera_id + region_id</li>
        <li><b>4 级回退策略</b>：model+camera+region → model+camera → model → global</li>
        <li><b>按操作类型阈值</b>：聚类 ≥3 样本、训练 ≥5 样本才使用当前隔离级</li>
        <li>隔离键从 anomaly → cluster → training run 全链路传播</li>
        <li>前端筛选器：支持按 model/camera/region 独立过滤</li>
      </ul>
    </td>
    <td width="50%">
      <h3>🛡 模型上线门禁</h3>
      <ul>
        <li><b>自动回归评估</b>：训练完成后自动触发门禁 Celery 任务</li>
        <li><b>4 项准入标准</b>：召回率 ≥95%、召回下降 ≤2%、抑制率提升 ≥10%、零真实缺陷误杀</li>
        <li><b>分层评估</b>：按 camera_id 分层的 Stratified 指标</li>
        <li>Holdout 评估集：从已审核 cluster 自动构建 Ground Truth</li>
        <li>门禁失败阻断部署，仅通过模型可进入 Canary 阶段</li>
      </ul>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <h3>🔁 在线↔离线数据闭环</h3>
      <ul>
        <li><b>NG 自动上传</b>：检测完成后 daemon 线程异步 POST 到离线平台，不阻塞主流程</li>
        <li><b>模型自动加载</b>：指向部署目录即可自动发现 <code>model.pt</code>，mtime 缓存自动失效</li>
        <li><b>训练完成自动门禁 → 部署</b>：训练 → 门禁评估 → 通过后自动 Canary 部署</li>
        <li><b>原子部署</b>：模型文件先写 <code>.tmp</code> 再 rename，防止在线系统读到不完整文件</li>
        <li><b>部署桥接</b>：<code>DeploymentService</code> 执行实际文件拷贝至配置的部署目标目录</li>
      </ul>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <h3>🎛 Cascading Budget + Identity Linking</h3>
      <ul>
        <li><b>两级预算控制</b>：Proposal Budget (自适应阈值 + K 上限) + Filter Budget (动态 per-patch 调度 full/partial/skip_all/emergency)，Filter EMA 耗时估计</li>
        <li><b>DefectTracker</b>：6态生命周期 (BIRTH→ACTIVE→TENTATIVE→MATURE→LOST→DEAD)，Kalman + 特征余弦级联匹配</li>
        <li><b>冲突解决</b>：Best Match Wins (1:N) / NMS Merge (N:1) / Feature Tiebreaker (N:M) / Hungarian (Race)</li>
        <li>MATURE identity (≥5帧) 触发上传，后续帧 PATCH 更新，跨相机 identity 合并去重</li>
      </ul>
    </td>
    <td width="50%">
      <h3>📐 Unified Embedding Space + Calibration</h3>
      <ul>
        <li><b>EmbeddingSpaceContract</b>：协议层 representation standard (384d, L2, cosine, DINOv2 geometry)</li>
        <li><b>Feature Calibration Layer</b>：CameraNormalizer (per-camera per-channel 标准化) → EmbeddingProjector (EAD features → PCA 384d) → WhiteningTransform (ZCA 去相关) → EMAFeatureCenter (缺陷中心追踪)</li>
        <li><b>三模态 Filter</b>：image + EAD raw + unified_emb → 768d fusion → 二分类，Feature Dropout 保证 fallback</li>
        <li>离线聚类 (DINOv2) 与在线推理 (EAD projected) 共享同一 embedding geometry</li>
        <li>EMA 特征中心：跨机位 defect_type 中心追踪，支持 KNN 检索 + 新缺陷发现 (is_novel)</li>
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
├── backend/                          # Python 后端（160+ 文件）
│   ├── app/
│   │   ├── api/                      # 17 个 FastAPI 路由，65+ 端点
│   │   │   ├── anomaly/              #   上传 · 列表 · 详情 · 重新处理
│   │   │   ├── cluster/              #   列表 · 详情 · 可视化 · 触发聚类
│   │   │   ├── review/               #   提交复核 · 查询历史
│   │   │   ├── embedding/            #   按异常 ID / 向量相似检索
│   │   │   ├── knowledge/            #   增删改查 · 全文搜索 · 按簇查询
│   │   │   ├── rules/                #   增删改查 · 在线评估 · 开关 · 从知识库生成
│   │   │   ├── training/             #   分类器训练 · 度量学习训练 · 状态查询
│   │   │   ├── registry/             #   部署 · 回滚 · 部署历史
│   │   │   ├── multimodal/           #   VLM 单簇 · 批量 · 单异常分析
│   │   │   ├── taxonomy/             #   🌳 缺陷分类树 · 统计 · 自动分类
│   │   │   ├── graph/                #   🕸 相似度图谱 · 邻居 · 路径 · 子图
│   │   │   ├── mask_refinement/      #   🧹 背景消除 · 图像标准化
│   │   │   ├── gate/                 #   🛡 门禁状态 · 评估报告 · 手动触发
│   │   │   └── hot_reload/           #   🔴 热重载信号 · A/B 切换 · 回滚
│   │   ├── domain/                   # 8 个领域模型 + Protocol 接口
│   │   ├── services/                 # 16 个业务服务模块
│   │   │   ├── gate/                 #   🛡 模型门禁评估（召回率/抑制率/分层）
│   │   │   ├── mask_refinement/      #   🧹 背景消除 + 🔀 双轨对比
│   │   │   └── ...
│   │   ├── repositories/             # 12 个 Repository（封装所有 DB 访问）
│   │   ├── models/                   # 14 个 SQLAlchemy ORM 表（含 pgvector）
│   │   ├── schemas/                  # Pydantic v2 请求/响应 Schema
│   │   ├── workers/                  # 14 个 Celery Worker 模块
│   │   │   ├── gate_worker/          #   🛡 门禁评估任务
│   │   │   └── ...
│   │   ├── infrastructure/           # 数据库 · MinIO · pgvector · Celery · 配置
│   │   ├── core/                     # 配置类 · 异常体系 · 安全工具
│   │   ├── common/                   # 共享类型 · structlog 结构化日志 · 🔒 数据隔离工具
│   │   └── tests/                    # pytest-asyncio（11 个测试套件，70 用例）
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
└── ml/                               # ML 模块（18 文件）
    ├── embedding/                    # DINOv2-S 提取器（384 维）
    ├── clustering/                   # UMAP + HDBSCAN Pipeline
    ├── classifier/                   # Filter Classifier
    │   ├── dual_modal/               #   Dual-Modal Filter（图像+特征双模态）
    │   │   ├── model.py              #     MobileNetV3 + EfficientAD Feature → Late Fusion
    │   │   ├── trainer.py            #     FocalLoss + 双学习率 + Feature Dropout
    │   │   ├── dataset.py            #     图像 + EfficientAD 特征加载
    │   │   └── config.py             #     训练超参
    │   └── metric_learning.py        #   📐 ArcFace + Triplet Loss 度量学习
    ├── alignment/                    # 📐 Embedding Space 对齐
    │   ├── projector.py              #   AlignmentProjector (Transformer)
    │   ├── trainer.py                #   InfoNCE 对比学习训练
    │   ├── dataset.py                #   EAD+DINOv2 成对数据
    │   └── config.py                 #   AlignmentConfig
    └── vlm/                          # Qwen2.5-VL 多模态分析器
```
- `seat_defect_core/` 在线检测核心（含 `_protocol/` 共享协议子模块），详见下方

### seat_defect_core — 在线实时检测核心

```
seat_defect_core/
├── _protocol/                         # 共享数据协议（内嵌，零外部依赖）
│   ├── entities.py                 #   PatchProposal, EfficientADFeatures 等 dataclass
│   ├── canonical_proposal.py       #   CanonicalPatchProposal (schema_version + 归一化坐标)
│   ├── embedding_space.py          #   EmbeddingSpaceContract + UnifiedEmbedding
│   ├── serialization.py            #   JSON/dict 序列化
│   └── types.py                    #   类型别名
├── runtime_config_parsers.py         # JSON / INI 配置解析器
├── config_file.py                    # 配置文件加载入口
├── rule_engine.py                    # 规则引擎：阈值条件命中 + 动作执行
├── anomaly_uploader.py               # NG 结果 fire-and-forget 上传至离线平台
├── fusion.py                         # 多机位融合判定
├── serialization.py                  # 检测结果序列化（含 filter_result）
├── api.py                            # SeatDefectInspector 入口，含自动上传调度
├── calibration/                      # 🎯 特征校准层（跨机位特征统一）
│   ├── camera_normalizer.py          #   CameraNormalizer — 机位级 per-channel 标准化
│   ├── projector.py                  #   EmbeddingProjector — EAD 多尺度特征 → 384-dim
│   ├── whitening.py                  #   WhiteningTransform — ZCA 白化去相关
│   ├── feature_center.py             #   EMAFeatureCenter — 缺陷类型特征中心 EMA
│   ├── registry.py                   #   CalibrationRegistry — 统一校准入口
│   └── config.py                     #   CalibrationConfig
├── classifier/
│   ├── __init__.py
│   └── engine.py                     # DualModalFilter 推理引擎：图像+特征双模态 + 故障安全
├── proposal/                         # 🔬 Region Proposal 模块
│   ├── generator.py                  #   热力图→连通域→区域裁剪
│   ├── budget.py                     #   BudgetController（三态自适应阈值）
│   ├── aggregation.py                #   加权聚合 (area × score)
│   └── config.py                     #   Proposal + BudgetConfig 配置
├── tracking/                         # 🔗 Defect Identity 追踪模块
│   ├── identity.py                   #   6态生命周期 (BIRTH→DEAD)
│   ├── tracker.py                    #   DefectTracker 编排器
│   ├── matcher.py                    #   级联匹配 + 冲突解决
│   ├── kalman_filter.py              #   6-DOF Kalman + Hungarian
│   └── config.py                     #   TrackConfig
├── service/
│   ├── core.py                       # InspectionService + ModelBundleCache（含分类器缓存/自动加载）
│   ├── inspection_camera.py          # 单机位检测流程（含分类器推理 + 规则引擎接入）
│   ├── inspection.py                 # 多机位检测编排
│   └── ...
├── types/                            # 类型定义（FramePacket, CameraInspectionResult 等）
├── yolo/                             # YOLO 检测模块
├── efficientad/                       # EfficientAD 异常检测模块
├── cvops/                            # 图像预处理（ROI / 质量 / 区域分割）
└── artifacts/                        # 调试产物生成
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
| **MLflow** | `5001` | 模型注册与实验追踪 |

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

# 1. 启动基础设施（Docker）
docker compose -f backend/docker-compose.yml up -d
# → 启动 PostgreSQL / Redis / MinIO / MLflow / Celery Worker

# 2. 后端 API
cd backend
cp .env.example .env
uv sync                                       # 自动创建 .venv + 安装所有依赖
uv run alembic upgrade head                   # 数据库迁移
uv run uvicorn app.main:app --reload --port 8000  # → http://localhost:8000

# 3. 前端
cd frontend
pnpm install && pnpm run dev                  # → http://localhost:3000

# 4. 在线检测核心
cd seat_defect_core && uv sync && cd ..
./seat_defect_core/.venv/bin/python -m seat_defect_core \
  --config seat_defect_core/config.example.json \
  --images "cam_front=sample.jpg"
```

---

## API 总览

> 所有端点文档详见 **[`/docs`](http://localhost:8000/docs)**（Swagger）和 **[`/redoc`](http://localhost:8000/redoc)**

```
                     POST   /api/anomaly/upload                    📥 上传异常
                     POST   /api/anomaly/upload-with-files         (在线核心 fire-and-forget 上传)
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

                     GET    /api/gates/status/{model_version_id}  🛡 模型门禁
                     GET    /api/gates/report/{model_version_id}
                     POST   /api/gates/evaluate

                     GET    /api/model/deploy-targets              📦 模型部署
                     POST   /api/model/deploy
                     POST   /api/model/deploy/{target}/rollback

                     POST   /api/multimodal/analyze/cluster/{id}    🤖 多模态分析
                     POST   /api/multimodal/analyze/batch
                     POST   /api/multimodal/analyze/anomaly/{id}

                     POST   /api/taxonomy/init                         🌳 缺陷分类树
                     GET    /api/taxonomy/tree · /tree/stats
                     CRUD   /api/taxonomy/nodes
                     POST   /api/taxonomy/auto-classify
                     POST   /api/taxonomy/link-knowledge

                     POST   /api/graph/build                           🕸 相似度图谱
                     GET    /api/graph/build/status
                     GET    /api/graph/neighbors/{anomaly_id}
                     POST   /api/graph/path
                     GET    /api/graph/subgraph/{anomaly_id}

                     POST   /api/training/metric-learning/start         📐 度量学习训练

                     POST   /api/mask-refinement/refine/{id}            🧹 Mask 精化
                     POST   /api/mask-refinement/refine-batch

                     POST   /api/hot-reload/signal/{target}             🔴 热重载
                     GET    /api/hot-reload/signal/{target}
                     PUT    /api/hot-reload/manifest/{target}
                     POST   /api/hot-reload/promote/{target}
                     POST   /api/hot-reload/rollback/{target}
                     GET    /api/hot-reload/targets
```

---

## 前端页面

| 页面 | 路由 | 功能说明 |
|:---|:---:|---|
| **Dashboard** | `/` | Plotly UMAP 散点图 · 复核状态分布柱状图 · 4 个统计指标卡片 |
| **Cluster Review** | `/clusters` | 聚类列表筛选 (seat_model/camera/region) · 详情弹窗 · 双轨对比弹窗 · 一键复核 |
| **Anomaly Browser** | `/anomalies` | seat_model/camera/region/状态筛选 · PhotoView 图片浏览（缩放/旋转） · 相似检索 |
| **Anomaly Upload** | `/upload` | JSON 元数据提交 · multipart 文件上传（原图/ROI/热力图/裁剪图） |
| **Knowledge Base** | `/knowledge` | 条目增删改查 · 全文搜索 · 按分类/缺陷类型筛选 · 一键生成规则 |
| **Rules Engine** | `/rules` | 规则增删改查 · 启停开关 · 在线评估模拟器 · 从知识库生成规则 |
| **Training** | `/training` | 模型列表 · 架构/超参配置启动训练 · 状态轮询（5s） · 🛡 门禁状态 + 详细报告弹窗 |
| **Model Deploy** | `/deploy` | 部署历史一览 · 选择模型/版本/目标部署 · 🔴 热重载状态面板 (Checksum/完整性/Canary/回滚) |

---

## 端到端 Demo

```bash
# 1. 启动离线平台基础设施 + Worker
docker compose -f backend/docker-compose.yml up -d

# 2. 启动后端 API（终端 2）
cd backend && uv run uvicorn app.main:app --reload --port 8000

# 3. 安装 seat_defect_core 并准备图片
cd seat_defect_core && uv sync && cd ..
mkdir -p sample_images
# 放入测试图片，文件名 = camera_id，如 cam_front.jpg

# 4. 运行端到端 Demo
./seat_defect_core/.venv/bin/python scripts/demo_full_loop.py \
  --backend http://localhost:8000 --images ./sample_images
```

---

## 在线↔离线数据闭环

本平台实现了完整的 **在线检测 → 离线学习 → 模型反哺** 数据飞轮。

### 闭环流程

```
1. 在线 NG → seat_defect_core 检测到 NG 后，daemon 线程异步上传
   ROI 图片 + PatchProposals + EfficientAD 特征到 POST /api/anomaly/upload-with-files
                    ↓
2. Mask Refine → GrabCut 背景消除 + CLAHE 光照标准化
                    ↓
3. Embedding   → Celery Worker 提取 DINOv2-S 384 维特征向量
                    ↓
4. 相似度图谱  → KNN 图谱构建，支持邻居查询和路径导航
                    ↓
5. 聚类分析    → UMAP + HDBSCAN 无监督发现缺陷模式
                    ↓
6. VLM 解释    → Qwen2.5-VL 多模态大模型自动解释每个簇
                    ↓
7. 人工复核    → 工程师确认缺陷 / 标记误报 / 拆分合并簇
   → 确认缺陷时自动关联 🌳 缺陷分类树节点
                    ↓
8. 知识库 + 规则 → 缺陷模式沉淀 + 规则自动生成
                    ↓
9. 分类器训练  → Filter Classifier (MobileNetV3) 二元分类
   度量学习    → ArcFace/Triplet Loss 缺陷嵌入学习 (可选)
                    ↓
10. 模型门禁   → 🛡 自动回归评估：召回率/抑制率/分层指标
   → 门禁失败阻断部署，仅通过模型可进入下一步
                    ↓
11. 模型注册   → MLflow 模型注册 + 版本管理
                    ↓
12. Canary 部署 → Celery 部署至 Shadow 目标，原子写入 (.tmp → rename)
                    ↓
13. 热重载信号 → reload.signal + manifest.json + SHA256 Checksum
   支持 Canary Promote 和版本回滚
                    ↓
14. 在线加载   → seat_defect_core 检测 reload.signal 热加载新模型，
   Filter Classifier 抑制 EfficientAD 误报 → 降低误报率
                    ↓
                   ↺ 循环往复，持续进化
```

### 配置在线核心

在 `seat_defect_core` 的检测配置中启用数据闭环：

```json
{
  "seat_defect_inspection": {
    "upload_base_url": "http://offline-platform:8000",
    "cameras": [{
      "camera_id": "line_a_cam_01",
      "filter_classifier": {
        "enabled": true,
        "model_path": "./deployed_models/line_a/filter_classifier/",
        "device": "cuda",
        "input_size": 448,
        "confidence_threshold": 0.5
      },
      "proposal": {
        "heatmap_threshold_mode": "adaptive",
        "heatmap_adaptive_std_multiplier": 1.5,
        "min_component_area": 16,
        "max_proposals": 20,
        "context_padding_ratio": 0.10,
        "aggregation_method": "weighted_confidence"
      },
      "rule_engine": {
        "enabled": true,
        "rules": [
          {
            "name": "low_evidence_false_alarm",
            "max_anomaly_score": 0.8,
            "require_filter_false_alarm": true,
            "action": "suppress_to_ok"
          }
        ]
      }
    }]
  }
}
```

> **关键设计**：Three-Modal Filter **只抑制不提升** — 仅在 EfficientAD 报 NG 时介入，通过图像+EAD特征+Unified Embedding 三模态判定，若判定为误报则降级为 OK，绝不将 OK 改为 NG。Feature Dropout 保证 fallback。推理失败时默认 `is_real_defect=True`（故障安全）。Region Proposal 将 ROI 拆分为独立 defect patch，加权聚合得出最终判定。

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
| **统一数据协议** | `seat_defect_core/_protocol/` 定义 `PatchProposal` 统一数据契约，内嵌于在线核心，在线推理和离线训练共享同一套数据结构 |
| **特征校准层** | `seat_defect_core/calibration/` 跨机位特征统一：Normalize → Project → Whiten → EMA Center，消除机位间特征分布差异 |
| **严格分层架构** | API 层只处理 HTTP，零数据库访问、零业务逻辑 |
| **Protocol 接口抽象** | `EmbeddingExtractor` 和 `VLMAnalyzer` 采用 Protocol 定义，替换模型无需改动业务代码 |
| **全链路异步** | Async FastAPI + async SQLAlchemy + async MinIO，CPU/GPU 密集型任务全部交 Celery Worker 异步执行 |
| **Repository 模式** | 所有 DB 访问封装在类型安全的 Repository 中，测试可直接用 SQLite 内存库替代 |
| **零硬编码** | Pydantic Settings 从环境变量读取所有配置，禁止 `DB_HOST = "localhost"` |
| **结构化日志** | structlog 输出 JSON 行日志，绑定 `trace_id` `cluster_id` `anomaly_id` `model_version` `camera_id` 上下文 |
| **Embedding 空间统一** | `EmbeddingSpaceContract` 定义 representation standard，在线 (EAD projected) 和离线 (DINOv2) 共享同一 geometry |

---

## 环境变量

完整列表见 [`backend/.env.example`](backend/.env.example)。

| 变量 | 默认值 | 说明 |
|---|---|---|
| `INDUSTRIAL_POSTGRES_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/anomaly_db` | PostgreSQL 连接 |
| `INDUSTRIAL_REDIS_URL` | `redis://localhost:6379/0` | Redis 缓存 |
| `INDUSTRIAL_CELERY_BROKER_URL` | `redis://localhost:6379/1` | Celery 消息队列 |
| `INDUSTRIAL_CELERY_RESULT_BACKEND` | `redis://localhost:6379/2` | Celery 结果存储 |
| `INDUSTRIAL_MINIO_ENDPOINT` | `localhost:9000` | MinIO 对象存储 |
| `INDUSTRIAL_MLFLOW_TRACKING_URI` | `http://localhost:5001` | MLflow 模型注册 |
| `INDUSTRIAL_VLM_ENDPOINT` | `http://localhost:8001/v1` | VLM 推理端点 |
| `INDUSTRIAL_DEFAULT_DEPLOY_TARGET` | `production_line_a` | 默认部署目标 |
| `INDUSTRIAL_DEPLOY_TARGETS` | `{"production_line_a":"./deployed_models/line_a"}` | 部署目标映射 |
| `INDUSTRIAL_DEPLOY_MODEL_SUBDIR` | `filter_classifier` | 模型子目录 |
| `INDUSTRIAL_DEPLOY_ON_TRAIN_COMPLETE` | `false` | 训练后自动部署 |
| `INDUSTRIAL_DEPLOY_AUTO_STRATEGY` | `canary` | 自动部署策略 (canary/direct) |
| `INDUSTRIAL_GATE_ENABLED` | `true` | 启用模型上线门禁 |
| `INDUSTRIAL_GATE_MIN_RECALL` | `0.95` | 门禁最低召回率 |
| `INDUSTRIAL_GATE_MAX_RECALL_DROP` | `0.02` | 门禁最大召回下降 |
| `INDUSTRIAL_GATE_MIN_SUPPRESSION_GAIN` | `0.10` | 门禁最小抑制率提升 |
| `INDUSTRIAL_ISOLATION_CLUSTERING_MIN_SAMPLES` | `3` | 聚类最小隔离样本数 |
| `INDUSTRIAL_ISOLATION_TRAINING_MIN_SAMPLES` | `5` | 训练最小隔离样本数 |
| `INDUSTRIAL_EMBEDDING_DIM` | `384` | Embedding 维度 |
| `INDUSTRIAL_DEBUG` | `false` | 调试模式 |

---

## 测试

```bash
cd backend
uv run pytest -v                                  # 全部 70 个测试用例
uv run pytest app/tests/ -v --cov=app             # 含覆盖率报告
uv run pytest app/tests/test_anomaly_service.py -v  # 单独文件
```

| 测试套件 | 覆盖内容 |
|---|---|
| `test_exceptions` | 全部 10 种异常类型及其错误码 |
| `test_anomaly_repository` | 创建、按ID查询、更新状态、不存在记录 |
| `test_clustering_service` | 默认配置、自定义配置 |
| `test_knowledge_service` | 创建条目、从复核自动生成、搜索 |
| `test_rule_engine` | CRUD、优先级评估、启停开关、相机过滤 |
| `test_anomaly_service` | 创建异常、含文件上传、列表查询过滤、重新处理 |
| `test_api` | 健康检查、空列表、资源不存在、无结果搜索 |
| `test_e2e_pipeline` | 异常上传隔离字段、Embedding+聚类全流程、审核+训练数据、门禁指标、隔离键传播 |
| `test_clustering_stability` | 固定 seed 确定性、分离簇检测、样本不足全噪声、代表样本选取 |
| `test_hot_reload` | SHA256 checksum 计算/校验、manifest 读写/回滚绑定、信号发送/清除/完整性 |
| `test_model_loading` | TorchScript 创建/加载/推理、预处理 pipeline、embedding 维度 (DINOv2-S 384)、故障安全 |

---

## 参与贡献

欢迎提交 Issue 和 Pull Request。各组件独立管理依赖：

```bash
cd backend && uv sync          # 后端依赖
cd seat_defect_core && uv sync # 在线检测核心依赖
cd backend && uv run pytest    # 运行测试
cd backend && uv run mypy app  # 类型检查
cd backend && uv run ruff check app  # 代码检查
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
