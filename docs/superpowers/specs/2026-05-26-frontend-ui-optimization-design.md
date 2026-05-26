# 前端交互与样式全面优化 — 设计文档

**日期**: 2026-05-26
**范围**: 9 个 feature 页面 + Layout + 全局样式基础设施
**风格**: 现代工业风（DataDog/Linear 参考）

---

## 一、总览

分 3 个 Layer 递进实施，每层独立可验证：

| Layer | 范围 | 目标 |
|-------|------|------|
| L1 | `index.css` + `tailwind.config.js` + 全局组件 | 建立 CSS 变量体系、三态统一组件（Skeleton/Empty/Error）、清理内联样式 |
| L2 | `layout.tsx` + `router.tsx` + `App.tsx` | 侧边栏升级、sticky Header + 面包屑、页面过渡动画、ScrollToTop |
| L3 | 9 个 feature 页面 | 各页面按独立方向进行交互和布局优化 |

---

## 二、Layer 1：基础设施

### 2.1 CSS 变量体系

在 `index.css` 的 `@tailwind utilities` 之后定义全局 tokens：

```css
:root {
  /* 品牌色 */
  --color-primary: #1677ff;
  --color-primary-hover: #4096ff;
  --color-primary-active: #0958d9;

  /* 功能色（工业语义） */
  --color-defect: #ff4d4f;
  --color-false-alarm: #52c41a;
  --color-pending: #faad14;
  --color-neutral: #8c8c8c;

  /* 表面层级 */
  --color-bg-layout: #f5f5f5;
  --color-bg-container: #ffffff;
  --color-bg-elevated: #ffffff;

  /* 阴影 */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.04);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.06);
  --shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.08);

  /* 圆角 */
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;

  /* 侧边栏 */
  --sider-bg: #0d1117;
  --sider-width: 220px;
  --sider-collapsed-width: 64px;
}
```

### 2.2 Tailwind 配置同步

在 `tailwind.config.js` 中扩展 `extend` 桥接 CSS 变量，使 `bg-primary`、`text-defect`、`shadow-md` 等 class 可用。

### 2.3 三态统一

所有页面的 loading/empty/error 三态替换为统一模式：

| 状态 | 组件 | 规范 |
|------|------|------|
| Loading | `<Skeleton>` | 表格页用 `Skeleton.Input` + `Skeleton.Button` 模拟表格骨架；卡片页用 `Skeleton.Image` |
| Empty | `<Empty>` | 带插画 + 引导性 description + 可选 CTA 按钮 |
| Error | `<Result status="error">` | 带重试按钮，subTitle 说明错误原因 |

### 2.4 内联样式清理

目标：所有 `style={{ }}` 替换为 Tailwind class。涉及约 80+ 处。

---

## 三、Layer 2：Layout & 导航

### 3.1 侧边栏

- 背景色 `#0d1117`，Logo 区域底部 `border-b border-white/10`
- 选中菜单项：左侧 3px `--color-primary` 指示条 + 轻微背景高亮
- 折叠状态写入 `localStorage`，key: `sider-collapsed`
- 折叠时 hover 显示 Ant Design `Tooltip` 展示完整菜单名
- 菜单项间距 2px

### 3.2 Header

- `position: sticky; top: 0; z-index: 10` 跟随滚动
- 左侧：自动面包屑（从 `react-router-dom` 的 `useMatches` 派生）
- 右侧：用户头像 + 当前时间（`dayjs` 实时更新）
- 底部 `border-b border-gray-100`

### 3.3 页面过渡

```css
@keyframes page-enter {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}
.page-transition {
  animation: page-enter 0.25s ease-out;
}
```

包裹 `<Content>` 区域，路由变化时触发。

### 3.4 ScrollToTop

监听 `location.pathname` 变化 → `window.scrollTo(0, 0)`。

---

## 四、Layer 3：页面精细优化

### 4.1 数据面板 Dashboard

**方向**：保持现有布局

| 项目 | 优化 |
|------|------|
| 统计卡片 | 数字 `countUp` 动画（用 `useEffect` + `requestAnimationFrame`）；颜色语义修正：缺陷红(`#ff4d4f`)、误报绿(`#52c41a`)、待审橙(`#faad14`) |
| 图表卡片 | 标题统一中文 |
| 空数据 | `<Empty description="暂无聚类数据">` + `Button`"运行聚类任务" |

### 4.2 聚类审核 ClusterReview

**方向**：双栏详情面板

| 项目 | 优化 |
|------|------|
| 布局 | `Row` 分栏，左 40% 紧凑表格 + 右 60% 详情面板（内联，不用 Modal） |
| 左侧表格 | sticky header，行可点击高亮选中 |
| 右侧面板 | 缩略图 Gallery、审核操作区、历史审核记录 Timeline |
| 双轨对比 | 从 Modal 改为右侧面板内的 `Drawer` 或可展开 Section |
| 空状态 | 未选中聚类时右侧显示 `<Empty description="选择左侧聚类查看详情">` |

### 4.3 异常浏览 AnomalyBrowser

**方向**：图片卡片网格

| 项目 | 优化 |
|------|------|
| 布局 | CSS Grid 响应式卡片网格（`grid-template-columns: repeat(auto-fill, minmax(280px, 1fr))`） |
| 卡片内容 | 缩略图（占卡片 60% 高度）+ 底部信息栏：相机 ID Tag、异常分数 Progress、时间戳 |
| 图片查看 | 点击卡片 → `react-photo-view` 全屏查看器（缩放/拖拽/左右切换） |
| 视图切换 | 顶部筛选栏右侧添加 `Segmented`：网格 / 表格 |
| 表格模式 | 保留原有 `AnomalyTable` + `AnomalyDetailModal` |
| 筛选栏 | 输入框 debounce 时显示 spinning 指示器 |

### 4.4 知识库 KnowledgeBase

**方向**：侧边分类导航

| 项目 | 优化 |
|------|------|
| 布局 | `Row` 分栏：左 240px 侧边分类 + 右内容区 |
| 左侧 | 类别树（`Tree` 组件）：全部、缺陷、误报、相机问题、光照、工艺；下方缺陷类型多选 |
| 右侧 | 卡片列表（替代表格），每张卡片：标题、摘要（2 行截断）、缺陷类型 Tag、日期 |
| 搜索 | 固定在右侧顶部，debounce 300ms，搜索中显示 Skeleton |
| 新建/详情 | 保持 Modal 形式 |

### 4.5 规则引擎 RulesEngine

**方向**：可视化规则构建器

| 项目 | 优化 |
|------|------|
| 条件构建 | 行内拼接：`[字段 Select] [运算符 Select] [值 Input]`，多条件间 `AND`/`OR` Toggle |
| 条件展示 | 每行规则以 `Tag.Group` 展示条件链，可展开查看详情 |
| 评估面板 | 命中规则绿色高亮 + 匹配样本数；未命中红色 + 零匹配提示 |
| 评估结果 | 替换 JSON dump，用 `Statistic` + `Descriptions` 结构化展示 |
| 创建/编辑 | Modal 内表单，条件构建区域支持动态增删行（`Form.List`） |

### 4.6 训练管理 Training

**方向**：添加任务日志面板

| 项目 | 优化 |
|------|------|
| 布局 | `Row` 分栏：左 55% 模型列表 + 右 45% 日志面板 |
| 左侧 | 保持 Tabs（已训练模型 / 过滤器 / PatchCore） |
| 右侧日志 | 暗色 terminal 风格（`bg-gray-900 text-green-400`），自动滚动到最新，轮询刷新 |
| PatchCore 上传 | 拖拽区 hover 动画 + 上传后缩略图预览 + 文件数量 badge |
| 状态弹窗 | 添加轮询进度条动画 |
| Tab 切换 | CSS transition fadeIn |

### 4.7 在线检测 Inspection

**方向**：保持现有布局

| 项目 | 优化 |
|------|------|
| 上传区 | 拖拽 hover 时边框变色 + `scale(1.01)` 过渡；已上传文件显示缩略图 |
| 检测进度 | `Steps` 组件："配置 → 上传 → 检测 → 完成"，当前步骤 `status="process"` |
| 结果展示 | 相机结果图用 `react-photo-view` 可点击放大 |
| 异常分数条 | 保持 Progress 样式，添加动画过渡 |
| 整体判定 | `Result` 组件展示 OK/NG（大图标 + 颜色），替代当前 Tag |

### 4.8 模型部署 ModelDeploy

**方向**：部署拓扑图

| 项目 | 优化 |
|------|------|
| 拓扑图 | 顶部 SVG/CSS 绘制的拓扑图：`目标节点` → 连线 → `当前活跃模型` → 虚线 → `影子模型`（如有） |
| 节点状态 | 颜色编码：绿=已同步、橙=待重载、红=异常、灰=无影子 |
| 热重载表格 | 保留但改为可折叠 Section |
| 部署历史 | 保持表格，列增加时间戳格式化 |
| 点击节点 | 展开该目标的详细配置 Drawer |

### 4.9 相机配置 CameraConfig

**方向**：拓扑连线图

| 项目 | 优化 |
|------|------|
| 拓扑图 | 顶部：`座椅型号` → `相机列表` → `YOLO/PatchCore/Filter 模型绑定` 三级节点 + 连线 |
| 图例 | 三种模型类型用不同颜色连线：蓝=YOLO、紫=PatchCore、绿=Filter |
| 列表选中态 | 左侧 3px `--color-primary` 蓝色指示条 |
| 分区模式 | Switch 切换时，区域模型表单用 `Collapse` 过渡展开/收起 |
| 模型选择 | 抽取 `ModelSelect` 复用组件（当前 YOLO/PatchCore/Filter 选择器重复 3 次） |
| 注册模型 | 保持 Modal |

---

## 五、技术约束

- **不引入新依赖**（除 `countUp` 动画用原生实现，react-photo-view 已安装）
- **不修改 API 层**（`api/`、`hooks/queries.ts`、`types/` 不变）
- 拓扑图用纯 SVG + CSS 实现，不引入 D3/G6 等图库
- 所有改动在 `src/` 目录内，不动 `vite.config.ts`、`package.json` 等

---

## 六、实施顺序

```
L1 → L2 → L3
          ├─ 4.1 Dashboard
          ├─ 4.2 ClusterReview
          ├─ 4.3 AnomalyBrowser
          ├─ 4.4 KnowledgeBase
          ├─ 4.5 RulesEngine
          ├─ 4.6 Training
          ├─ 4.7 Inspection
          ├─ 4.8 ModelDeploy
          └─ 4.9 CameraConfig
```

L3 各页面按复杂度排序：简单页面先行（Dashboard、Inspection），复杂页面靠后（RulesEngine、ModelDeploy、CameraConfig）。
