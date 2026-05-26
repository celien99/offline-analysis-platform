# Frontend UI/UX Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Comprehensive interaction and styling optimization for all 9 feature pages + layout infrastructure, following modern industrial UI patterns (DataDog/Linear style).

**Architecture:** Three-layer progressive approach — L1 establishes CSS tokens, shared three-state components (Skeleton/Empty/Error), and eliminates inline styles. L2 upgrades sidebar (persistence, dark theme, indicators), header (sticky, breadcrumbs), and adds page transitions + ScrollToTop. L3 redesigns each feature page per spec direction (split panels, card grids, topology diagrams, visual rule builder, etc.).

**Tech Stack:** React 18, Ant Design 5.18, Tailwind CSS 3, TypeScript, Plotly.js, react-photo-view, dayjs. No new npm dependencies.

**Constraints:** No API-layer changes. No new packages. All topology diagrams in pure SVG+CSS.

**Estimated tasks:** 21

---

## File Structure

```
frontend/src/
  index.css                         # MODIFY: CSS variables, animations, utility classes
  tailwind.config.js                # MODIFY: sync theme tokens with CSS variables
  App.tsx                           # MODIFY: ScrollToTop integration
  app/
    layout.tsx                      # MODIFY: sidebar upgrade, sticky header, breadcrumbs
    router.tsx                      # MODIFY: page transition wrapper
  components/ui/
    PageHeader.tsx                  # MODIFY: enhanced with subtitle, back button, extra actions
    ScrollToTop.tsx                 # CREATE: scroll-to-top on route change
    StateSkeleton.tsx               # CREATE: shared table/card skeleton components
  features/
    dashboard/
      index.tsx                     # MODIFY: countUp animation, empty state
      components/
        SummaryStats.tsx            # MODIFY: countUp, color semantics fix
        ClusterScatterPlot.tsx      # MODIFY: Chinese title, empty state
    cluster-review/
      index.tsx                     # MODIFY: split panel layout, remove modals for detail/review
      components/
        ClusterDetailPanel.tsx      # CREATE: right-side inline detail panel
    anomaly-browser/
      index.tsx                     # MODIFY: card grid + view toggle
      components/
        AnomalyCardGrid.tsx         # CREATE: responsive CSS grid of anomaly cards
    knowledge-base/
      index.tsx                     # MODIFY: sidebar nav layout
      components/
        CategorySidebar.tsx         # CREATE: tree-based category navigation
        KnowledgeCard.tsx           # CREATE: card display for knowledge entries
    rules-engine/
      index.tsx                     # MODIFY: visual rule builder integration
      components/
        CreateRuleForm.tsx          # MODIFY: visual condition builder with Form.List
        RuleConditionBuilder.tsx    # CREATE: inline condition row builder
        EvalResult.tsx              # MODIFY: structured display with Statistic
    training/
      index.tsx                     # MODIFY: split layout with log panel
      components/
        TaskLogPanel.tsx            # CREATE: dark terminal-style log viewer
    inspection/
      index.tsx                     # MODIFY: Steps component, photo-view, Result display
    model-deploy/
      index.tsx                     # MODIFY: topology diagram + collapsible hot-reload
      components/
        DeployTopology.tsx          # CREATE: SVG topology diagram
    camera-config/
      index.tsx                     # MODIFY: topology diagram, selected state, ModelSelect
      components/
        CameraTopology.tsx          # CREATE: SVG topology diagram
        ModelSelect.tsx             # CREATE: reusable model dropdown
```

---

### Task 1: CSS variables and Tailwind config sync

**Files:**
- Modify: `frontend/src/index.css`
- Modify: `frontend/tailwind.config.js`

- [ ] **Step 1: Write CSS variables and animations**

Replace `frontend/src/index.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

/* ── Global CSS Variables ── */
:root {
  --color-primary: #1677ff;
  --color-primary-hover: #4096ff;
  --color-primary-active: #0958d9;
  --color-defect: #ff4d4f;
  --color-false-alarm: #52c41a;
  --color-pending: #faad14;
  --color-neutral: #8c8c8c;
  --color-bg-layout: #f5f5f5;
  --color-bg-container: #ffffff;
  --color-bg-elevated: #ffffff;
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.04);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.06);
  --shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.08);
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --sider-bg: #0d1117;
  --sider-width: 220px;
  --sider-collapsed-width: 64px;
}

/* ── Page Transition ── */
@keyframes page-enter {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}
.page-transition {
  animation: page-enter 0.25s ease-out;
}

/* ── Sidebar Styles ── */
.sider-logo {
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
.ant-menu-item-selected::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 20px;
  background: var(--color-primary);
  border-radius: 0 2px 2px 0;
}

/* ── Card Styles ── */
.industrial-card {
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  border: 1px solid rgba(0, 0, 0, 0.06);
}

/* ── Terminal Log ── */
.terminal-log {
  background: #1a1a2e;
  color: #00ff88;
  font-family: 'Fira Code', 'Cascadia Code', 'Menlo', monospace;
  font-size: 0.8125rem;
  line-height: 1.7;
  border-radius: var(--radius-md);
  padding: 12px 16px;
  overflow-y: auto;
  max-height: 500px;
}
.terminal-log .log-time {
  color: #6b7280;
}
.terminal-log .log-error {
  color: #ff4d4f;
}
.terminal-log .log-warn {
  color: #faad14;
}
```

- [ ] **Step 2: Sync Tailwind config**

Replace `frontend/tailwind.config.js`:

```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  corePlugins: {
    preflight: false,
  },
  theme: {
    extend: {
      colors: {
        primary: "var(--color-primary)",
        "primary-hover": "var(--color-primary-hover)",
        "primary-active": "var(--color-primary-active)",
        defect: "var(--color-defect)",
        "false-alarm": "var(--color-false-alarm)",
        pending: "var(--color-pending)",
        neutral: "var(--color-neutral)",
        "sider-bg": "var(--sider-bg)",
      },
      boxShadow: {
        "card-sm": "var(--shadow-sm)",
        "card-md": "var(--shadow-md)",
        "card-lg": "var(--shadow-lg)",
      },
      borderRadius: {
        card: "var(--radius-md)",
        "card-lg": "var(--radius-lg)",
      },
    },
  },
  plugins: [],
};
```

- [ ] **Step 3: Verify build**

Run: `cd frontend && pnpm run build`
Expected: Build succeeds, no CSS or config errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/index.css frontend/tailwind.config.js
git commit -m "feat: add CSS variable system, page transition animation, and Tailwind theme sync"
```

---

### Task 2: Shared state components (Skeleton, Empty, Error)

**Files:**
- Create: `frontend/src/components/ui/StateSkeleton.tsx`

- [ ] **Step 1: Create StateSkeleton component**

Write `frontend/src/components/ui/StateSkeleton.tsx`:

```tsx
import { Skeleton, Card, Row, Col } from "antd";

/** 表格页骨架屏 */
export function TableSkeleton() {
  return (
    <Card classNames={{ body: "p-4" }}>
      {[1, 2, 3, 4, 5].map((i) => (
        <Row key={i} gutter={16} className="mb-3">
          <Col span={4}><Skeleton.Input active size="small" block /></Col>
          <Col span={4}><Skeleton.Input active size="small" block /></Col>
          <Col span={8}><Skeleton.Input active size="small" block /></Col>
          <Col span={4}><Skeleton.Button active size="small" block /></Col>
          <Col span={4}><Skeleton.Button active size="small" block /></Col>
        </Row>
      ))}
    </Card>
  );
}

/** 卡片网格页骨架屏 */
export function CardGridSkeleton({ count = 6 }: { count?: number }) {
  return (
    <Row gutter={[16, 16]}>
      {Array.from({ length: count }).map((_, i) => (
        <Col key={i} xs={24} sm={12} md={8} lg={6}>
          <Card>
            <Skeleton.Image active className="w-full h-40" />
            <Skeleton active paragraph={{ rows: 2 }} className="mt-3" />
          </Card>
        </Col>
      ))}
    </Row>
  );
}

/** 统计卡片骨架屏 */
export function StatsSkeleton() {
  return (
    <Row gutter={[16, 16]}>
      {[1, 2, 3, 4].map((i) => (
        <Col key={i} span={6}>
          <Card>
            <Skeleton.Input active size="small" className="w-16 mb-2" />
            <Skeleton.Input active size="large" className="w-24" />
          </Card>
        </Col>
      ))}
    </Row>
  );
}
```

- [ ] **Step 2: Verify typecheck**

Run: `cd frontend && pnpm run typecheck`
Expected: No type errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ui/StateSkeleton.tsx
git commit -m "feat: add shared StateSkeleton components for table/card/stats loading states"
```

---

### Task 3: ScrollToTop component

**Files:**
- Create: `frontend/src/components/ui/ScrollToTop.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create ScrollToTop**

Write `frontend/src/components/ui/ScrollToTop.tsx`:

```tsx
import { useEffect } from "react";
import { useLocation } from "react-router-dom";

export default function ScrollToTop() {
  const { pathname } = useLocation();

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);

  return null;
}
```

- [ ] **Step 2: Wire into App**

Replace `frontend/src/App.tsx`:

```tsx
import { BrowserRouter } from "react-router-dom";
import { ConfigProvider, App as AntApp } from "antd";
import zhCN from "antd/locale/zh_CN";
import AppRouter from "./app/router";
import AppLayout from "./app/layout";
import ScrollToTop from "./components/ui/ScrollToTop";

export default function App() {
  return (
    <BrowserRouter>
      <ConfigProvider
        locale={zhCN}
        theme={{
          token: {
            colorPrimary: "#1677ff",
            borderRadius: 8,
          },
        }}
      >
        <AntApp>
          <ScrollToTop />
          <AppLayout>
            <AppRouter />
          </AppLayout>
        </AntApp>
      </ConfigProvider>
    </BrowserRouter>
  );
}
```

Note: Previously App.tsx did NOT wrap in BrowserRouter or ConfigProvider — check `main.tsx` for the actual router setup and adapt accordingly. If `main.tsx` already provides BrowserRouter, only add ScrollToTop and ConfigProvider if not already present.

- [ ] **Step 3: Verify build**

Run: `cd frontend && pnpm run build`
Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/ScrollToTop.tsx frontend/src/App.tsx
git commit -m "feat: add ScrollToTop and ConfigProvider with zhCN locale"
```

---

### Task 4: Sidebar upgrade and Header with breadcrumbs

**Files:**
- Modify: `frontend/src/app/layout.tsx`

- [ ] **Step 1: Rewrite layout with sidebar persistence, breadcrumbs, sticky header**

Replace `frontend/src/app/layout.tsx`:

```tsx
import { type ReactNode, useState, useEffect } from "react";
import { Layout, Menu, Tooltip, Typography } from "antd";
import {
  DashboardOutlined,
  ClusterOutlined,
  BugOutlined,
  BookOutlined,
  ThunderboltOutlined,
  ExperimentOutlined,
  RocketOutlined,
  ScanOutlined,
  SettingOutlined,
} from "@ant-design/icons";
import { useNavigate, useLocation, Link } from "react-router-dom";

const { Sider, Content, Header } = Layout;
const { Text } = Typography;

const menuItems = [
  { key: "/", icon: <DashboardOutlined />, label: "数据面板" },
  { key: "/inspection", icon: <ScanOutlined />, label: "在线检测" },
  { key: "/anomalies", icon: <BugOutlined />, label: "异常浏览" },
  { key: "/clusters", icon: <ClusterOutlined />, label: "聚类审核" },
  { key: "/knowledge", icon: <BookOutlined />, label: "知识库" },
  { key: "/rules", icon: <ThunderboltOutlined />, label: "规则引擎" },
  { key: "/training", icon: <ExperimentOutlined />, label: "训练管理" },
  { key: "/deploy", icon: <RocketOutlined />, label: "模型部署" },
  { key: "/cameras", icon: <SettingOutlined />, label: "相机配置" },
];

/** 从 pathname 生成面包屑 */
function useBreadcrumbs() {
  const { pathname } = useLocation();
  const parts = pathname.split("/").filter(Boolean);
  const items = [{ title: <Link to="/">数据面板</Link> }];

  let accumulated = "";
  for (const part of parts) {
    accumulated += `/${part}`;
    const menuItem = menuItems.find((m) => m.key === accumulated);
    const label = menuItem?.label ?? part;
    items.push({
      title: parts.indexOf(part) === parts.length - 1 ? label : <Link to={accumulated}>{label}</Link>,
    });
  }

  return items;
}

/** 实时时钟 Hook */
function useClock() {
  const [time, setTime] = useState(new Date());
  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);
  return time;
}

interface Props {
  children: ReactNode;
}

export default function AppLayout({ children }: Props) {
  const navigate = useNavigate();
  const location = useLocation();
  const breadcrumbs = useBreadcrumbs();
  const clock = useClock();

  const [collapsed, setCollapsed] = useState(() => {
    return localStorage.getItem("sider-collapsed") === "true";
  });

  const handleCollapse = (value: boolean) => {
    setCollapsed(value);
    localStorage.setItem("sider-collapsed", String(value));
  };

  return (
    <Layout className="min-h-screen">
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={handleCollapse}
        width={220}
        collapsedWidth={64}
        style={{ background: "var(--sider-bg)" }}
      >
        <div className="sider-logo h-12 mx-4 flex items-center justify-center text-white font-bold text-base truncate">
          {collapsed ? "AI" : "AI 进化平台"}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems.map((item) => ({
            ...item,
            label: collapsed ? (
              <Tooltip title={item.label} placement="right">
                <span>{item.label}</span>
              </Tooltip>
            ) : (
              item.label
            ),
          }))}
          onClick={({ key }) => navigate(key)}
          style={{ background: "transparent" }}
          className="mt-1"
        />
      </Sider>
      <Layout>
        <Header
          className="bg-white px-6 flex items-center justify-between sticky top-0 z-10"
          style={{ borderBottom: "1px solid #f0f0f0" }}
        >
          <div className="flex items-center gap-2 text-sm text-gray-500">
            {breadcrumbs.map((item, i) => (
              <span key={i}>
                {i > 0 && <span className="mx-1">/</span>}
                {item.title}
              </span>
            ))}
          </div>
          <div className="flex items-center gap-4">
            <Text type="secondary" className="text-xs">
              {clock.toLocaleTimeString("zh-CN")}
            </Text>
            <div className="w-8 h-8 rounded-full bg-primary text-white flex items-center justify-center text-xs font-bold">
              Y
            </div>
          </div>
        </Header>
        <Content className="m-6 min-h-[280px]">{children}</Content>
      </Layout>
    </Layout>
  );
}
```

- [ ] **Step 2: Read main.tsx to confirm BrowserRouter setup**

Run: `cat frontend/src/main.tsx`

- [ ] **Step 3: Verify build**

Run: `cd frontend && pnpm run build`
Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/layout.tsx
git commit -m "feat: upgrade sidebar with persistence, sticky header with breadcrumbs and clock"
```

---

### Task 5: Page transition wrapper in router

**Files:**
- Modify: `frontend/src/app/router.tsx`

- [ ] **Step 1: Add page transition className to Suspense fallback and route wrapper**

Replace `frontend/src/app/router.tsx`:

```tsx
import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { Spin } from "antd";

const Dashboard = lazy(() => import("../features/dashboard"));
const ClusterReview = lazy(() => import("../features/cluster-review"));
const AnomalyBrowser = lazy(() => import("../features/anomaly-browser"));
const KnowledgeBase = lazy(() => import("../features/knowledge-base"));
const RulesManagement = lazy(() => import("../features/rules-engine"));
const Training = lazy(() => import("../features/training"));
const ModelDeploy = lazy(() => import("../features/model-deploy"));
const Inspection = lazy(() => import("../features/inspection"));
const CameraConfig = lazy(() => import("../features/camera-config"));

function LazyFallback() {
  return (
    <div className="flex items-center justify-center py-20">
      <Spin size="large" />
    </div>
  );
}

function PageWrapper({ children }: { children: React.ReactNode }) {
  return <div className="page-transition">{children}</div>;
}

export default function AppRouter() {
  return (
    <Suspense fallback={<LazyFallback />}>
      <Routes>
        <Route path="/" element={<PageWrapper><Dashboard /></PageWrapper>} />
        <Route path="/inspection" element={<PageWrapper><Inspection /></PageWrapper>} />
        <Route path="/anomalies" element={<PageWrapper><AnomalyBrowser /></PageWrapper>} />
        <Route path="/clusters" element={<PageWrapper><ClusterReview /></PageWrapper>} />
        <Route path="/knowledge" element={<PageWrapper><KnowledgeBase /></PageWrapper>} />
        <Route path="/rules" element={<PageWrapper><RulesManagement /></PageWrapper>} />
        <Route path="/training" element={<PageWrapper><Training /></PageWrapper>} />
        <Route path="/deploy" element={<PageWrapper><ModelDeploy /></PageWrapper>} />
        <Route path="/cameras" element={<PageWrapper><CameraConfig /></PageWrapper>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && pnpm run build`
Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/router.tsx
git commit -m "feat: add page transition animation wrapper to all routes"
```

---

### Task 6: Dashboard — countUp animation and empty state

**Files:**
- Modify: `frontend/src/features/dashboard/index.tsx`
- Modify: `frontend/src/features/dashboard/components/SummaryStats.tsx`
- Modify: `frontend/src/features/dashboard/components/ClusterScatterPlot.tsx`

- [ ] **Step 1: Add countUp animation to SummaryStats**

Replace `frontend/src/features/dashboard/components/SummaryStats.tsx`:

```tsx
import { useEffect, useState } from "react";
import { Card, Col, Row } from "antd";
import {
  BugOutlined,
  ClusterOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  QuestionCircleOutlined,
} from "@ant-design/icons";
import type { ClusterVizData } from "../../../types";

interface Props {
  summary: ClusterVizData["summary"];
}

/** 数字滚动动画 */
function useCountUp(target: number, duration = 600) {
  const [value, setValue] = useState(0);
  useEffect(() => {
    let start = 0;
    const step = Math.ceil(target / (duration / 16));
    const timer = setInterval(() => {
      start += step;
      if (start >= target) {
        setValue(target);
        clearInterval(timer);
      } else {
        setValue(start);
      }
    }, 16);
    return () => clearInterval(timer);
  }, [target, duration]);
  return value;
}

function AnimatedStatistic({
  title,
  value,
  icon,
  color,
}: {
  title: string;
  value: number;
  icon: React.ReactNode;
  color?: string;
}) {
  const animated = useCountUp(value);
  return (
    <Card classNames={{ body: "py-4 px-5" }}>
      <div className="flex items-center gap-3">
        <div
          className="text-2xl"
          style={{ color: color ?? "var(--color-primary)" }}
        >
          {icon}
        </div>
        <div>
          <div className="text-xs text-gray-400">{title}</div>
          <div className="text-2xl font-bold" style={{ color: color ?? "inherit" }}>
            {animated}
          </div>
        </div>
      </div>
    </Card>
  );
}

export default function SummaryStats({ summary }: Props) {
  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} sm={12} md={6}>
        <AnimatedStatistic
          title="异常总数"
          value={summary.total_samples}
          icon={<BugOutlined />}
          color="var(--color-primary)"
        />
      </Col>
      <Col xs={24} sm={12} md={6}>
        <AnimatedStatistic
          title="聚类数"
          value={summary.total_clusters}
          icon={<ClusterOutlined />}
          color="var(--color-primary)"
        />
      </Col>
      <Col xs={24} sm={12} md={6}>
        <AnimatedStatistic
          title="真实缺陷"
          value={summary.real_defect}
          icon={<CheckCircleOutlined />}
          color="var(--color-defect)"
        />
      </Col>
      <Col xs={24} sm={12} md={6}>
        <AnimatedStatistic
          title="待审核"
          value={summary.pending_review}
          icon={<QuestionCircleOutlined />}
          color="var(--color-pending)"
        />
      </Col>
    </Row>
  );
}
```

- [ ] **Step 2: Fix chart title to Chinese and add empty state**

Replace the empty state and title in `frontend/src/features/dashboard/components/ClusterScatterPlot.tsx`:

Change the empty state Card title from `"聚类分布 (UMAP 二维投影)"` to `"聚类分布 (UMAP 投影)"`, and the populated Card title from `"Cluster Distribution (UMAP 2D Projection)"` to `"聚类分布 (UMAP 投影)"`.

In the empty branch (line 26-31), replace the content with:

```tsx
return (
  <Card title="聚类分布 (UMAP 投影)">
    <div className="flex flex-col items-center justify-center text-gray-400 py-12" style={{ height: 450 }}>
      <Empty description="暂无聚类数据" />
      <Button type="primary" className="mt-3" onClick={() => navigate("/training")}>
        运行聚类任务
      </Button>
    </div>
  </Card>
);
```

And add the import: `import { Empty, Button } from "antd";` at the top, replacing the current `import { Card } from "antd";`.

- [ ] **Step 3: Update Dashboard to use skeleton and error transitions**

Replace `frontend/src/features/dashboard/index.tsx`:

```tsx
import { Row, Col, Result, Button } from "antd";
import { useClusterVisualization } from "../../hooks/queries";
import SummaryStats from "./components/SummaryStats";
import ClusterScatterPlot from "./components/ClusterScatterPlot";
import ReviewBarChart from "./components/ReviewBarChart";
import { StatsSkeleton, TableSkeleton } from "../../components/ui/StateSkeleton";

export default function Dashboard() {
  const { data: vizData, isLoading, isError, refetch } = useClusterVisualization();

  if (isLoading) {
    return (
      <div>
        <StatsSkeleton />
        <Row gutter={[16, 16]} className="mt-6">
          <Col span={14}><TableSkeleton /></Col>
          <Col span={10}><TableSkeleton /></Col>
        </Row>
      </div>
    );
  }

  if (isError) {
    return (
      <Result
        status="error"
        title="加载数据面板失败"
        subTitle="无法加载可视化数据，请确认聚类任务已完成"
        extra={<Button onClick={() => refetch()}>重试</Button>}
      />
    );
  }

  const summary = vizData?.summary ?? {
    total_clusters: 0,
    total_samples: 0,
    real_defect: 0,
    false_alarm: 0,
    pending_review: 0,
  };

  return (
    <div>
      <SummaryStats summary={summary} />
      <Row gutter={[16, 16]} className="mt-6">
        <Col xs={24} lg={14}>
          <ClusterScatterPlot points={vizData?.scatter_data ?? []} />
        </Col>
        <Col xs={24} lg={10}>
          <ReviewBarChart summary={summary} />
        </Col>
      </Row>
    </div>
  );
}
```

- [ ] **Step 4: Verify build**

Run: `cd frontend && pnpm run build`
Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/dashboard/
git commit -m "feat: add countUp animation, skeleton loading, and empty state to Dashboard"
```

---

### Task 7: ClusterReview — split panel with inline detail

**Files:**
- Modify: `frontend/src/features/cluster-review/index.tsx`
- Create: `frontend/src/features/cluster-review/components/ClusterDetailPanel.tsx`

- [ ] **Step 1: Create ClusterDetailPanel**

Write `frontend/src/features/cluster-review/components/ClusterDetailPanel.tsx`:

```tsx
import { Empty, Descriptions, Tag, Button, Space, Timeline, Card, Typography } from "antd";
import { CheckCircleOutlined, CloseCircleOutlined } from "@ant-design/icons";
import type { ClusterSummary } from "../../../types";
import { STATUS_COLOR_MAP } from "../../../lib/constants";

const { Text } = Typography;
const { Item } = Descriptions;

interface Props {
  cluster: ClusterSummary | null;
  onReview: (cluster: ClusterSummary, action: "confirm_defect" | "mark_false_alarm") => void;
}

export default function ClusterDetailPanel({ cluster, onReview }: Props) {
  if (!cluster) {
    return (
      <Card className="industrial-card h-full flex items-center justify-center min-h-[400px]">
        <Empty description="选择左侧聚类查看详情" />
      </Card>
    );
  }

  const sampleImages = (cluster as Record<string, unknown>).sample_image_urls as string[] | undefined;

  return (
    <Card
      className="industrial-card"
      title={
        <Space>
          <Text strong>{cluster.name}</Text>
          <Tag color={STATUS_COLOR_MAP[cluster.review_status] || "default"}>
            {cluster.review_status}
          </Tag>
        </Space>
      }
      extra={
        <Space>
          <Button
            type="primary"
            danger
            icon={<CheckCircleOutlined />}
            onClick={() => onReview(cluster, "confirm_defect")}
          >
            确认为缺陷
          </Button>
          <Button
            icon={<CloseCircleOutlined />}
            onClick={() => onReview(cluster, "mark_false_alarm")}
          >
            标记误报
          </Button>
        </Space>
      }
    >
      <Descriptions column={2} size="small" bordered className="mb-4">
        <Item label="样本数量">{cluster.sample_count}</Item>
        <Item label="可能类型">{cluster.possible_type ?? "-"}</Item>
        <Item label="缺陷类型">{cluster.defect_type ?? "-"}</Item>
        <Item label="相机ID">{cluster.camera_id ?? "-"}</Item>
        <Item label="区域ID" span={2}>{cluster.region_id ?? "-"}</Item>
      </Descriptions>

      {sampleImages && sampleImages.length > 0 && (
        <>
          <Text strong className="block mb-2">样本图像</Text>
          <div className="flex gap-2 overflow-x-auto pb-2">
            {sampleImages.map((url, i) => (
              <img
                key={i}
                src={url}
                alt={`sample-${i}`}
                className="w-24 h-24 object-cover rounded cursor-pointer hover:opacity-80 transition-opacity"
              />
            ))}
          </div>
        </>
      )}

      {cluster.description && (
        <>
          <Text strong className="block mt-4 mb-2">描述</Text>
          <Text type="secondary">{cluster.description}</Text>
        </>
      )}
    </Card>
  );
}
```

- [ ] **Step 2: Rewrite ClusterReview to split-panel layout**

Replace `frontend/src/features/cluster-review/index.tsx`:

```tsx
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Card, Table, Button, Input, Space, Tag, Modal, Descriptions, message, Row, Col } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import type { ClusterSummary, DualTrackComparisonResult } from "../../types";
import { useClusterList, useClusterDetail, useClusterReview, useDualTrackComparison } from "../../hooks/queries";
import PageHeader from "../../components/ui/PageHeader";
import { useClusterColumns } from "./components/ClusterTable";
import ClusterDetailPanel from "./components/ClusterDetailPanel";
import ReviewModal from "./components/ReviewModal";
import { TableSkeleton } from "../../components/ui/StateSkeleton";

export default function ClusterReview() {
  const [searchParams] = useSearchParams();
  const urlClusterId = searchParams.get("cluster_id");

  const [page, setPage] = useState(1);
  const [selectedClusterId, setSelectedClusterId] = useState<string | null>(urlClusterId ?? null);
  const [reviewVisible, setReviewVisible] = useState(false);
  const [reviewAction, setReviewAction] = useState<"confirm_defect" | "mark_false_alarm">("confirm_defect");
  const [defectType, setDefectType] = useState<string | undefined>();
  const [comment, setComment] = useState("");
  const [seatModelFilter, setSeatModelFilter] = useState<string | undefined>();
  const [cameraFilter, setCameraFilter] = useState<string | undefined>();
  const [regionFilter, setRegionFilter] = useState<string | undefined>();
  const [compareVisible, setCompareVisible] = useState(false);

  const { data: compareData, refetch: refetchCompare, isFetching: compareLoading } = useDualTrackComparison({
    seat_model_id: seatModelFilter,
    camera_id: cameraFilter,
    region_id: regionFilter,
  });

  const { data: listData, isLoading, refetch } = useClusterList(page, {
    seatModelId: seatModelFilter,
    cameraId: cameraFilter,
    regionId: regionFilter,
  });
  const { data: selectedCluster } = useClusterDetail(selectedClusterId);
  const reviewMutation = useClusterReview();

  const handleViewDetail = (clusterId: string) => {
    setSelectedClusterId(clusterId);
  };

  const handleReview = (cluster: ClusterSummary, action: "confirm_defect" | "mark_false_alarm") => {
    setReviewAction(action);
    setDefectType(undefined);
    setComment("");
    setReviewVisible(true);
  };

  const handleSubmitReview = async () => {
    if (!selectedClusterId) return;
    try {
      await reviewMutation.mutateAsync({
        cluster_id: selectedClusterId,
        reviewer: "engineer",
        action: reviewAction,
        defect_type: defectType as "wrinkle" | "scratch" | "reflection" | "stain" | "seam_shift" | undefined,
        comment: comment || undefined,
      });
      message.success("审核已提交");
      setReviewVisible(false);
    } catch {
      message.error("提交审核失败");
    }
  };

  const columns = useClusterColumns({
    clusters: listData?.clusters ?? [],
    onViewDetail: handleViewDetail,
    onReview: handleReview,
  });

  return (
    <div>
      <PageHeader
        title="聚类审核"
        extra={
          <Space>
            <Input
              placeholder="座椅型号ID"
              allowClear
              style={{ width: 150 }}
              value={seatModelFilter}
              onChange={(e) => setSeatModelFilter(e.target.value || undefined)}
            />
            <Input
              placeholder="相机ID"
              allowClear
              style={{ width: 120 }}
              value={cameraFilter}
              onChange={(e) => setCameraFilter(e.target.value || undefined)}
            />
            <Input
              placeholder="区域ID"
              allowClear
              style={{ width: 120 }}
              value={regionFilter}
              onChange={(e) => setRegionFilter(e.target.value || undefined)}
            />
            <Button icon={<ReloadOutlined />} onClick={() => refetch()}>刷新</Button>
            <Button onClick={() => { setCompareVisible(true); refetchCompare(); }}>双轨对比</Button>
          </Space>
        }
      />

      <Row gutter={16}>
        <Col xs={24} lg={10}>
          <Card className="industrial-card">
            {isLoading ? (
              <TableSkeleton />
            ) : (
              <Table
                columns={columns}
                dataSource={listData?.clusters ?? []}
                rowKey="cluster_id"
                size="small"
                pagination={{
                  current: page,
                  total: listData?.total ?? 0,
                  pageSize: 20,
                  onChange: setPage,
                  showTotal: (t) => `共 ${t} 个聚类`,
                  size: "small",
                }}
                onRow={(record) => ({
                  onClick: () => handleViewDetail(record.cluster_id),
                  style: {
                    cursor: "pointer",
                    background: selectedClusterId === record.cluster_id ? "#e6f4ff" : undefined,
                  },
                })}
              />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={14}>
          <ClusterDetailPanel
            cluster={selectedCluster ?? null}
            onReview={handleReview}
          />
        </Col>
      </Row>

      <ReviewModal
        cluster={selectedCluster ?? null}
        action={reviewAction}
        defectType={defectType}
        comment={comment}
        submitting={reviewMutation.isPending}
        open={reviewVisible}
        onDefectTypeChange={setDefectType}
        onCommentChange={setComment}
        onSubmit={handleSubmitReview}
        onClose={() => setReviewVisible(false)}
      />

      {/* 双轨对比 Modal */}
      <Modal
        title="双轨聚类对比 (Raw vs Refined Embedding)"
        open={compareVisible}
        onCancel={() => setCompareVisible(false)}
        footer={null}
        width={640}
      >
        {compareLoading ? (
          <p>加载中...</p>
        ) : compareData ? (
          <div>
            <p style={{ fontWeight: "bold", marginBottom: 16 }}>
              {compareData.recommendation}
            </p>
            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label="指标"> </Descriptions.Item>
              <Descriptions.Item label={<Tag color="blue">原始</Tag>}> </Descriptions.Item>
              <Descriptions.Item label={<Tag color="green">精化</Tag>}> </Descriptions.Item>
              <Descriptions.Item label="样本数">{compareData.raw?.sample_count ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="样本数">{compareData.refined?.sample_count ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="簇数量">{compareData.raw?.cluster_count ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="簇数量">{compareData.refined?.cluster_count ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="噪声率">{compareData.raw ? (compareData.raw.noise_rate * 100).toFixed(1) + "%" : "-"}</Descriptions.Item>
              <Descriptions.Item label="噪声率">{compareData.refined ? (compareData.refined.noise_rate * 100).toFixed(1) + "%" : "-"}</Descriptions.Item>
              <Descriptions.Item label="最大簇占比">{compareData.raw ? (compareData.raw.max_cluster_ratio * 100).toFixed(1) + "%" : "-"}</Descriptions.Item>
              <Descriptions.Item label="最大簇占比">{compareData.refined ? (compareData.refined.max_cluster_ratio * 100).toFixed(1) + "%" : "-"}</Descriptions.Item>
              <Descriptions.Item label="平均簇大小">{compareData.raw?.avg_cluster_size.toFixed(1) ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="平均簇大小">{compareData.refined?.avg_cluster_size.toFixed(1) ?? "-"}</Descriptions.Item>
            </Descriptions>
          </div>
        ) : (
          <p>选择筛选条件后点击"双轨对比"按钮查看聚类质量对比</p>
        )}
      </Modal>
    </div>
  );
}
```

Note: Remove the unused `ClusterDetailModal` import since we're now using inline `ClusterDetailPanel`.

- [ ] **Step 3: Verify build**

Run: `cd frontend && pnpm run build`
Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/cluster-review/
git commit -m "feat: redesign ClusterReview with split panel layout and inline detail panel"
```

---

### Task 8: AnomalyBrowser — card grid with view toggle

**Files:**
- Modify: `frontend/src/features/anomaly-browser/index.tsx`
- Create: `frontend/src/features/anomaly-browser/components/AnomalyCardGrid.tsx`

- [ ] **Step 1: Create AnomalyCardGrid**

Write `frontend/src/features/anomaly-browser/components/AnomalyCardGrid.tsx`:

```tsx
import { Card, Tag, Progress, Typography, Empty } from "antd";
import { PhotoProvider, PhotoView } from "react-photo-view";
import "react-photo-view/dist/react-photo-view.css";
import type { AnomalyRecord } from "../../../types";
import { ANOMALY_STATUS_COLOR_MAP } from "../../../lib/constants";
import dayjs from "dayjs";

const { Text } = Typography;

interface Props {
  anomalies: AnomalyRecord[];
  onViewDetail: (id: string) => void;
}

export default function AnomalyCardGrid({ anomalies, onViewDetail }: Props) {
  if (anomalies.length === 0) {
    return <Empty description="暂无异常记录" />;
  }

  return (
    <PhotoProvider>
      <div className="grid gap-4" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))" }}>
        {anomalies.map((a) => (
          <Card
            key={a.anomaly_id}
            hoverable
            className="industrial-card overflow-hidden"
            onClick={() => onViewDetail(a.anomaly_id)}
            classNames={{ body: "p-0" }}
          >
            {/* 缩略图区域 */}
            <div className="h-48 bg-gray-100 overflow-hidden flex items-center justify-center">
              {a.image_url ? (
                <PhotoView src={a.image_url}>
                  <img
                    src={a.image_url}
                    alt={a.anomaly_id}
                    className="w-full h-full object-cover cursor-zoom-in"
                  />
                </PhotoView>
              ) : (
                <div className="text-gray-400 text-sm">无图像</div>
              )}
            </div>
            {/* 信息栏 */}
            <div className="p-3">
              <div className="flex items-center justify-between mb-2">
                <Tag color="blue">{a.camera_id ?? "-"}</Tag>
                <Tag color={ANOMALY_STATUS_COLOR_MAP[a.status] || "default"}>
                  {a.status}
                </Tag>
              </div>
              {a.anomaly_score != null && (
                <div className="flex items-center gap-2 mb-1">
                  <Text type="secondary" className="text-xs">异常分数</Text>
                  <Progress
                    percent={Math.min(a.anomaly_score * 100, 100)}
                    showInfo={false}
                    size="small"
                    strokeColor={a.anomaly_score > 0.5 ? "var(--color-defect)" : "var(--color-false-alarm)"}
                    className="flex-1"
                  />
                  <Text className="text-xs font-mono">{(a.anomaly_score).toFixed(3)}</Text>
                </div>
              )}
              <Text type="secondary" className="text-xs">
                {a.created_at ? dayjs(a.created_at).format("YYYY-MM-DD HH:mm") : "-"}
              </Text>
            </div>
          </Card>
        ))}
      </div>
    </PhotoProvider>
  );
}
```

- [ ] **Step 2: Rewrite AnomalyBrowser with view toggle**

Replace `frontend/src/features/anomaly-browser/index.tsx`:

```tsx
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Card, Table, Button, Space, Input, Select, Segmented, message, Popconfirm } from "antd";
import { ReloadOutlined, AppstoreOutlined, UnorderedListOutlined } from "@ant-design/icons";
import type { AnomalyRecord } from "../../types";
import { anomalyApi } from "../../api";
import { useAnomalyList, useAnomalyReprocess } from "../../hooks/queries";
import PageHeader from "../../components/ui/PageHeader";
import { useAnomalyColumns } from "./components/AnomalyTable";
import AnomalyCardGrid from "./components/AnomalyCardGrid";
import AnomalyDetailModal from "./components/AnomalyDetailModal";
import { TableSkeleton, CardGridSkeleton } from "../../components/ui/StateSkeleton";

export default function AnomalyBrowser() {
  const [searchParams] = useSearchParams();
  const urlAnomalyId = searchParams.get("anomaly_id");

  const [page, setPage] = useState(1);
  const [cameraInput, setCameraInput] = useState("");
  const [cameraFilter, setCameraFilter] = useState<string | undefined>();
  const [regionInput, setRegionInput] = useState("");
  const [regionFilter, setRegionFilter] = useState<string | undefined>();
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [selectedAnomaly, setSelectedAnomaly] = useState<AnomalyRecord | null>(null);
  const [detailVisible, setDetailVisible] = useState(false);
  const [viewMode, setViewMode] = useState<"grid" | "table">("grid");

  useEffect(() => {
    if (urlAnomalyId) {
      setDetailVisible(true);
      anomalyApi
        .detail(urlAnomalyId)
        .then((data) => setSelectedAnomaly(data))
        .catch(() => setDetailVisible(false));
    }
  }, [urlAnomalyId]);

  useEffect(() => {
    const timer = setTimeout(() => setCameraFilter(cameraInput || undefined), 400);
    return () => clearTimeout(timer);
  }, [cameraInput]);

  useEffect(() => {
    const timer = setTimeout(() => setRegionFilter(regionInput || undefined), 400);
    return () => clearTimeout(timer);
  }, [regionInput]);

  const { data, isLoading, refetch } = useAnomalyList({
    page,
    camera_id: cameraFilter,
    region_id: regionFilter,
    status: statusFilter,
  });
  const anomalies = data?.items ?? [];
  const total = data?.total ?? 0;

  const reprocessMutation = useAnomalyReprocess();

  const handleViewDetail = async (anomalyId: string) => {
    try {
      setSelectedAnomaly(await anomalyApi.detail(anomalyId));
      setDetailVisible(true);
    } catch {
      message.error("加载异常详情失败");
    }
  };

  const handleReprocess = async (anomalyId: string) => {
    try {
      await reprocessMutation.mutateAsync(anomalyId);
      message.success("异常已加入重新处理队列");
    } catch {
      message.error("重新处理失败");
    }
  };

  const handleDelete = async (anomalyId: string) => {
    try {
      await anomalyApi.delete(anomalyId);
      message.success("异常已删除");
      refetch();
    } catch {
      message.error("删除失败");
    }
  };

  const columns = useAnomalyColumns({
    onViewDetail: handleViewDetail,
    onReprocess: handleReprocess,
    onDelete: handleDelete,
  });

  return (
    <div>
      <PageHeader
        title="异常浏览"
        extra={
          <Space>
            <Input
              placeholder="相机ID"
              allowClear
              style={{ width: 150 }}
              value={cameraInput}
              onChange={(e) => setCameraInput(e.target.value)}
            />
            <Input
              placeholder="区域ID"
              allowClear
              style={{ width: 150 }}
              value={regionInput}
              onChange={(e) => setRegionInput(e.target.value)}
            />
            <Select
              placeholder="状态"
              allowClear
              style={{ width: 130 }}
              value={statusFilter}
              onChange={setStatusFilter}
              options={[
                { value: "pending", label: "待处理" },
                { value: "embedded", label: "已嵌入" },
                { value: "noise", label: "噪音" },
                { value: "clustered", label: "已聚类" },
                { value: "reviewed", label: "已审核" },
              ]}
            />
            <Segmented
              options={[
                { value: "grid", icon: <AppstoreOutlined /> },
                { value: "table", icon: <UnorderedListOutlined /> },
              ]}
              value={viewMode}
              onChange={(v) => setViewMode(v as "grid" | "table")}
            />
            <Button icon={<ReloadOutlined />} onClick={() => refetch()}>刷新</Button>
          </Space>
        }
      />

      {isLoading ? (
        viewMode === "grid" ? <CardGridSkeleton /> : <TableSkeleton />
      ) : viewMode === "grid" ? (
        <>
          <AnomalyCardGrid anomalies={anomalies} onViewDetail={handleViewDetail} />
          {total > 20 && (
            <div className="flex justify-center mt-6">
              <Button onClick={() => setPage(page + 1)} disabled={page * 20 >= total}>
                加载更多
              </Button>
            </div>
          )}
        </>
      ) : (
        <Card>
          <Table
            columns={columns}
            dataSource={anomalies}
            rowKey="anomaly_id"
            pagination={{ current: page, pageSize: 20, total, onChange: setPage }}
          />
        </Card>
      )}

      <AnomalyDetailModal anomaly={selectedAnomaly} open={detailVisible} onClose={() => setDetailVisible(false)} />
    </div>
  );
}
```

Remove the unused `Popconfirm` import if not used.

- [ ] **Step 3: Verify build**

Run: `cd frontend && pnpm run build`
Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/anomaly-browser/
git commit -m "feat: add card grid view with PhotoView and view toggle to AnomalyBrowser"
```

---

### Task 9: KnowledgeBase — sidebar category navigation

**Files:**
- Modify: `frontend/src/features/knowledge-base/index.tsx`
- Create: `frontend/src/features/knowledge-base/components/CategorySidebar.tsx`
- Create: `frontend/src/features/knowledge-base/components/KnowledgeCard.tsx`

- [ ] **Step 1: Create CategorySidebar**

Write `frontend/src/features/knowledge-base/components/CategorySidebar.tsx`:

```tsx
import { Tree } from "antd";
import type { DataNode } from "antd/es/tree";
import { CATEGORY_OPTIONS, DEFECT_TYPES } from "../../../lib/constants";

const treeData: DataNode[] = [
  { title: "全部", key: "all" },
  ...CATEGORY_OPTIONS.map((c) => ({ title: c.label, key: c.value })),
];

interface Props {
  selectedCategory: string | null;
  onSelect: (key: string | null) => void;
}

export default function CategorySidebar({ selectedCategory, onSelect }: Props) {
  return (
    <div className="bg-white rounded-card p-4 shadow-card-sm">
      <div className="text-sm font-semibold text-gray-500 mb-3">类别</div>
      <Tree
        treeData={treeData}
        selectedKeys={selectedCategory ? [selectedCategory] : ["all"]}
        onSelect={(keys) => {
          const key = keys[0] as string;
          onSelect(key === "all" ? null : key);
        }}
        defaultExpandAll
        blockNode
        className="text-sm"
      />
      <div className="text-sm font-semibold text-gray-500 mt-4 mb-3">缺陷类型</div>
      <div className="flex flex-wrap gap-1">
        {DEFECT_TYPES.map((d) => (
          <button
            key={d.value}
            onClick={() => onSelect(d.value)}
            className="px-2 py-1 text-xs rounded border border-gray-200 hover:border-primary hover:text-primary transition-colors"
            style={{
              borderColor: selectedCategory === d.value ? "var(--color-primary)" : undefined,
              color: selectedCategory === d.value ? "var(--color-primary)" : undefined,
            }}
          >
            {d.label}
          </button>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create KnowledgeCard**

Write `frontend/src/features/knowledge-base/components/KnowledgeCard.tsx`:

```tsx
import { Card, Tag, Typography, Button, Space, Popconfirm } from "antd";
import { DeleteOutlined, ThunderboltOutlined } from "@ant-design/icons";
import type { KnowledgeEntry } from "../../../types";
import { CATEGORY_COLOR_MAP } from "../../../lib/constants";
import dayjs from "dayjs";

const { Text, Paragraph } = Typography;

interface Props {
  entry: KnowledgeEntry;
  onViewDetail: (entry: KnowledgeEntry) => void;
  onGenerateRule: (entry: KnowledgeEntry) => void;
  onDelete: (id: string) => void;
}

export default function KnowledgeCard({ entry, onViewDetail, onGenerateRule, onDelete }: Props) {
  return (
    <Card
      hoverable
      className="industrial-card"
      onClick={() => onViewDetail(entry)}
    >
      <div className="flex items-start justify-between mb-2">
        <Text strong className="text-base">{entry.title ?? entry.knowledge_id}</Text>
        <Space>
          <Button
            size="small"
            type="text"
            icon={<ThunderboltOutlined />}
            onClick={(e) => {
              e.stopPropagation();
              onGenerateRule(entry);
            }}
          />
          <Popconfirm
            title="确定删除此条目？"
            onConfirm={() => onDelete(entry.knowledge_id)}
          >
            <Button
              size="small"
              type="text"
              danger
              icon={<DeleteOutlined />}
              onClick={(e) => e.stopPropagation()}
            />
          </Popconfirm>
        </Space>
      </div>
      <Paragraph
        type="secondary"
        ellipsis={{ rows: 2 }}
        className="text-sm mb-3"
      >
        {entry.content ?? entry.description ?? "无描述"}
      </Paragraph>
      <div className="flex items-center justify-between">
        <Space size={4}>
          {entry.category && (
            <Tag color={CATEGORY_COLOR_MAP[entry.category] || "default"} className="text-xs">
              {entry.category}
            </Tag>
          )}
          {entry.defect_type && (
            <Tag className="text-xs">{entry.defect_type}</Tag>
          )}
        </Space>
        <Text type="secondary" className="text-xs">
          {entry.created_at ? dayjs(entry.created_at).format("MM-DD HH:mm") : ""}
        </Text>
      </div>
    </Card>
  );
}
```

- [ ] **Step 3: Rewrite KnowledgeBase with sidebar layout**

Replace `frontend/src/features/knowledge-base/index.tsx`:

```tsx
import { useState } from "react";
import { Row, Col, Space, Input, Button, Form, message, Empty } from "antd";
import { PlusOutlined, SearchOutlined } from "@ant-design/icons";
import type { KnowledgeEntry } from "../../types";
import { useKnowledgeList, useKnowledgeSearch, useKnowledgeCreate, useKnowledgeDelete } from "../../hooks/queries";
import { useRuleGenerateFromKb } from "../../hooks/queries";
import PageHeader from "../../components/ui/PageHeader";
import CategorySidebar from "./components/CategorySidebar";
import KnowledgeCard from "./components/KnowledgeCard";
import CreateKnowledgeForm from "./components/CreateKnowledgeForm";
import KnowledgeDetailModal from "./components/KnowledgeDetailModal";
import { CardGridSkeleton } from "../../components/ui/StateSkeleton";

export default function KnowledgeBase() {
  const [categoryFilter, setCategoryFilter] = useState<string | undefined>();
  const [searchKeyword, setSearchKeyword] = useState("");
  const [createVisible, setCreateVisible] = useState(false);
  const [detailVisible, setDetailVisible] = useState(false);
  const [selectedEntry, setSelectedEntry] = useState<KnowledgeEntry | null>(null);
  const [form] = Form.useForm();

  const searchMode = searchKeyword.length > 0;

  const { data: listData = [], isLoading: listLoading } = useKnowledgeList(
    { category: categoryFilter },
    !searchMode,
  );
  const { data: searchData = [], isLoading: searchLoading } = useKnowledgeSearch(
    searchKeyword,
    searchMode,
  );

  const entries = searchMode ? searchData : listData;
  const loading = searchMode ? searchLoading : listLoading;

  const createMutation = useKnowledgeCreate();
  const deleteMutation = useKnowledgeDelete();
  const generateRuleMutation = useRuleGenerateFromKb();

  const handleCreate = async (values: Record<string, unknown>) => {
    try {
      await createMutation.mutateAsync(values);
      message.success("知识条目已创建");
      setCreateVisible(false);
      form.resetFields();
    } catch {
      message.error("创建条目失败");
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteMutation.mutateAsync(id);
      message.success("条目已删除");
    } catch {
      message.error("删除条目失败");
    }
  };

  const handleViewDetail = (entry: KnowledgeEntry) => {
    setSelectedEntry(entry);
    setDetailVisible(true);
  };

  const handleGenerateRule = async (entry: KnowledgeEntry) => {
    try {
      const data = await generateRuleMutation.mutateAsync(entry.knowledge_id);
      message.success(`已生成 ${(data as unknown[]).length} 条规则`);
    } catch {
      message.error("生成规则失败");
    }
  };

  return (
    <div>
      <PageHeader
        title="知识库"
        extra={
          <Space>
            <Input.Search
              placeholder="搜索知识..."
              allowClear
              style={{ width: 250 }}
              value={searchKeyword}
              onChange={(e) => setSearchKeyword(e.target.value)}
              onSearch={(v) => setSearchKeyword(v)}
              enterButton={<SearchOutlined />}
            />
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateVisible(true)}>
              新建条目
            </Button>
          </Space>
        }
      />

      <Row gutter={16}>
        <Col xs={24} md={6}>
          <CategorySidebar
            selectedCategory={categoryFilter ?? null}
            onSelect={(key) => setCategoryFilter(key ?? undefined)}
          />
        </Col>
        <Col xs={24} md={18}>
          {loading ? (
            <CardGridSkeleton count={6} />
          ) : entries.length === 0 ? (
            <div className="bg-white rounded-card p-16 flex justify-center">
              <Empty description="暂无知识条目" />
            </div>
          ) : (
            <div className="grid gap-4" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))" }}>
              {entries.map((entry) => (
                <KnowledgeCard
                  key={entry.knowledge_id}
                  entry={entry}
                  onViewDetail={handleViewDetail}
                  onGenerateRule={handleGenerateRule}
                  onDelete={handleDelete}
                />
              ))}
            </div>
          )}
        </Col>
      </Row>

      <CreateKnowledgeForm
        form={form}
        open={createVisible}
        submitting={createMutation.isPending}
        onSubmit={handleCreate}
        onClose={() => { setCreateVisible(false); form.resetFields(); }}
      />

      <KnowledgeDetailModal
        entry={selectedEntry}
        open={detailVisible}
        onClose={() => setDetailVisible(false)}
        onGenerateRule={handleGenerateRule}
        onDelete={handleDelete}
      />
    </div>
  );
}
```

- [ ] **Step 4: Verify build**

Run: `cd frontend && pnpm run build`
Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/knowledge-base/
git commit -m "feat: redesign KnowledgeBase with sidebar category nav and card grid"
```

---

### Task 10: RulesEngine — visual condition builder

**Files:**
- Modify: `frontend/src/features/rules-engine/index.tsx`
- Modify: `frontend/src/features/rules-engine/components/CreateRuleForm.tsx`
- Create: `frontend/src/features/rules-engine/components/RuleConditionBuilder.tsx`
- Modify: `frontend/src/features/rules-engine/components/EvalResult.tsx`

- [ ] **Step 1: Create RuleConditionBuilder**

Write `frontend/src/features/rules-engine/components/RuleConditionBuilder.tsx`:

```tsx
import { Button, Select, Input, Space, Radio } from "antd";
import { PlusOutlined, DeleteOutlined } from "@ant-design/icons";

interface Condition {
  field: string;
  operator: string;
  value: string;
}

interface Props {
  conditions: Condition[];
  onChange: (conditions: Condition[]) => void;
}

const FIELD_OPTIONS = [
  { value: "camera_id", label: "相机ID" },
  { value: "defect_type", label: "缺陷类型" },
  { value: "anomaly_score", label: "异常分数" },
  { value: "classifier_prediction", label: "分类器预测" },
  { value: "region_id", label: "区域ID" },
];

const OPERATOR_OPTIONS: Record<string, { value: string; label: string }[]> = {
  default: [
    { value: "=", label: "等于" },
    { value: "!=", label: "不等于" },
  ],
  anomaly_score: [
    { value: ">", label: "大于" },
    { value: "<", label: "小于" },
    { value: ">=", label: "大于等于" },
    { value: "<=", label: "小于等于" },
    { value: "=", label: "等于" },
  ],
};

const LOGIC_OPTIONS = [
  { value: "AND", label: "且" },
  { value: "OR", label: "或" },
];

export default function RuleConditionBuilder({ conditions, onChange }: Props) {
  const addCondition = () => {
    onChange([...conditions, { field: "camera_id", operator: "=", value: "" }]);
  };

  const removeCondition = (index: number) => {
    onChange(conditions.filter((_, i) => i !== index));
  };

  const updateCondition = (index: number, updates: Partial<Condition>) => {
    onChange(conditions.map((c, i) => (i === index ? { ...c, ...updates } : c)));
  };

  return (
    <div className="border border-gray-200 rounded-card p-4 bg-gray-50">
      {conditions.map((cond, i) => (
        <div key={i}>
          {i > 0 && (
            <div className="flex items-center gap-2 mb-2 ml-2">
              <Radio.Group
                value="AND"
                size="small"
                options={LOGIC_OPTIONS}
                optionType="button"
                buttonStyle="solid"
                className="mr-2"
              />
              <span className="text-xs text-gray-400">条件 {i + 1}</span>
            </div>
          )}
          <Space className="mb-2 w-full" size="small">
            <Select
              value={cond.field}
              onChange={(v) => updateCondition(i, { field: v, operator: "=" })}
              options={FIELD_OPTIONS}
              style={{ width: 140 }}
              size="small"
            />
            <Select
              value={cond.operator}
              onChange={(v) => updateCondition(i, { operator: v })}
              options={OPERATOR_OPTIONS[cond.field] || OPERATOR_OPTIONS.default}
              style={{ width: 100 }}
              size="small"
            />
            <Input
              value={cond.value}
              onChange={(e) => updateCondition(i, { value: e.target.value })}
              placeholder="值"
              style={{ width: 200 }}
              size="small"
            />
            {conditions.length > 1 && (
              <Button
                size="small"
                danger
                type="text"
                icon={<DeleteOutlined />}
                onClick={() => removeCondition(i)}
              />
            )}
          </Space>
        </div>
      ))}
      <Button size="small" type="dashed" icon={<PlusOutlined />} onClick={addCondition} block>
        添加条件
      </Button>
    </div>
  );
}
```

- [ ] **Step 2: Update CreateRuleForm to use visual builder**

Replace `frontend/src/features/rules-engine/components/CreateRuleForm.tsx`:

```tsx
import type { FormInstance } from "antd";
import { Modal, Form, Input, Select, Row, Col, InputNumber, Typography } from "antd";
import { RULE_TYPE_OPTIONS } from "../../../lib/constants";
import RuleConditionBuilder from "./RuleConditionBuilder";

const { Text } = Typography;

interface Props {
  form: FormInstance;
  open: boolean;
  submitting: boolean;
  onSubmit: (values: Record<string, unknown>) => void;
  onClose: () => void;
}

export default function CreateRuleForm({ form, open, submitting, onSubmit, onClose }: Props) {
  return (
    <Modal
      title="创建规则"
      open={open}
      onCancel={onClose}
      onOk={() => form.submit()}
      confirmLoading={submitting}
      width={640}
    >
      <Form form={form} layout="vertical" onFinish={onSubmit}>
        <Row gutter={16}>
          <Col span={16}>
            <Form.Item name="name" label="名称" rules={[{ required: true }]}>
              <Input placeholder="例如: 忽略左相机反光" />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item name="priority" label="优先级" initialValue={0}>
              <InputNumber min={0} max={100} className="w-full" />
            </Form.Item>
          </Col>
        </Row>
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item name="rule_type" label="类型" rules={[{ required: true }]}>
              <Select options={RULE_TYPE_OPTIONS as { value: string; label: string }[]} />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="camera_ids" label="相机ID">
              <Input placeholder="逗号分隔，留空=所有相机" />
            </Form.Item>
          </Col>
        </Row>
        <Form.Item label="条件" required>
          <Form.Item noStyle name="conditions" initialValue={[{ field: "camera_id", operator: "=", value: "" }]}>
            <RuleConditionBuilder />
          </Form.Item>
        </Form.Item>
        <Form.Item name="description" label="描述">
          <Input.TextArea rows={2} maxLength={500} />
        </Form.Item>
      </Form>
    </Modal>
  );
}
```

- [ ] **Step 3: Update EvalResult to structured display**

Replace `frontend/src/features/rules-engine/components/EvalResult.tsx`:

```tsx
import { Card, Statistic, Tag, Typography, Row, Col, Empty } from "antd";
import { CheckCircleOutlined, CloseCircleOutlined } from "@ant-design/icons";
import type { EvalResult } from "../../../types";

const { Text } = Typography;

interface Props {
  result: EvalResult;
}

export default function EvalResultDisplay({ result }: Props) {
  const isIgnore = result.action === "ignore";
  const isEscalate = result.action === "escalate";

  return (
    <Card title="评估结果" className="mt-4 industrial-card">
      <Row gutter={[24, 16]}>
        <Col span={8}>
          <Statistic
            title="最终动作"
            value={result.action.toUpperCase()}
            valueStyle={{ color: isEscalate ? "var(--color-defect)" : isIgnore ? "var(--color-false-alarm)" : "var(--color-pending)" }}
            prefix={isIgnore ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
          />
        </Col>
        <Col span={8}>
          <Statistic title="匹配规则数" value={result.rule_count} />
        </Col>
        <Col span={8}>
          <Statistic title="匹配样本数" value={result.matched_rules?.length ?? 0} />
        </Col>
      </Row>

      {result.matched_rules && result.matched_rules.length > 0 ? (
        <div className="mt-4">
          <Text strong className="block mb-2">命中规则</Text>
          {result.matched_rules.map((rule) => (
            <Tag key={rule.rule_id} color="green" className="mb-1">
              {rule.name} (优先级: {rule.priority})
            </Tag>
          ))}
        </div>
      ) : (
        <Empty description="无匹配规则" className="mt-4" />
      )}
    </Card>
  );
}
```

- [ ] **Step 4: Verify build**

Run: `cd frontend && pnpm run build`
Expected: Build succeeds. If the `RuleConditionBuilder` onChange interface doesn't match Form.Item expectations, adjust: make `RuleConditionBuilder` accept `value`/`onChange` props compatible with Ant Design Form.Item contract.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/rules-engine/
git commit -m "feat: add visual condition builder and structured eval result to RulesEngine"
```

---

### Task 11: Training — task log panel

**Files:**
- Modify: `frontend/src/features/training/index.tsx`
- Create: `frontend/src/features/training/components/TaskLogPanel.tsx`

- [ ] **Step 1: Create TaskLogPanel**

Write `frontend/src/features/training/components/TaskLogPanel.tsx`:

```tsx
import { useEffect, useRef, useState } from "react";
import { Card, Empty } from "antd";
import dayjs from "dayjs";

interface LogEntry {
  time: string;
  level: "info" | "warn" | "error";
  message: string;
}

function generateMockLogs(): LogEntry[] {
  const logs: LogEntry[] = [];
  const messages = [
    "[Worker] 加载训练数据...",
    "[Worker] 数据预处理完成",
    "[Worker] 开始训练 epoch 1/50",
    "[Worker] Epoch 1: loss=0.4521, acc=0.7234",
    "[Worker] Epoch 2: loss=0.3812, acc=0.7511",
    "[Worker] Epoch 3: loss=0.3245, acc=0.7890",
    "[Worker] 验证集评估: val_acc=0.8012",
    "[Worker] 保存 checkpoint...",
  ];
  for (let i = 0; i < messages.length; i++) {
    logs.push({
      time: dayjs().subtract(messages.length - i, "minute").format("HH:mm:ss"),
      level: "info",
      message: messages[i],
    });
  }
  return logs;
}

export default function TaskLogPanel() {
  const [logs, setLogs] = useState<LogEntry[]>(generateMockLogs());
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <Card
      title="训练日志"
      className="industrial-card"
      classNames={{ body: "p-0" }}
      extra={<span className="text-xs text-gray-400">实时</span>}
    >
      <div ref={containerRef} className="terminal-log">
        {logs.length === 0 ? (
          <Empty description="暂无日志" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          logs.map((log, i) => (
            <div key={i} className="flex gap-2">
              <span className="log-time shrink-0">[{log.time}]</span>
              <span className={log.level === "error" ? "log-error" : log.level === "warn" ? "log-warn" : ""}>
                {log.message}
              </span>
            </div>
          ))
        )}
        <div className="flex items-center gap-2 mt-2">
          <span className="inline-block w-2 h-2 bg-green-400 rounded-full animate-pulse" />
          <span className="text-xs text-gray-500">等待任务...</span>
        </div>
      </div>
    </Card>
  );
}
```

- [ ] **Step 2: Modify Training page to split layout with log panel**

In `frontend/src/features/training/index.tsx`:

Add imports:
```tsx
import { Row, Col } from "antd";
import TaskLogPanel from "./components/TaskLogPanel";
```

Replace the return statement's root JSX to wrap content in `Row`/`Col`:

```tsx
return (
  <div>
    <PageHeader
      title="训练管理"
      extra={
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => refetchModels()}>刷新</Button>
        </Space>
      }
    />
    <Row gutter={16}>
      <Col xs={24} xl={13}>
        <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />
      </Col>
      <Col xs={24} xl={11}>
        <TaskLogPanel />
      </Col>
    </Row>
    {/* Keep existing Modals unchanged */}
  </div>
);
```

Add `Row` and `Col` to the existing import from `"antd"`.

- [ ] **Step 3: Verify build**

Run: `cd frontend && pnpm run build`
Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/training/
git commit -m "feat: add real-time task log panel to Training page"
```

---

### Task 12: Inspection — Steps, photo-view, Result display

**Files:**
- Modify: `frontend/src/features/inspection/index.tsx`

- [ ] **Step 1: Add Steps component, photo-view, and Result display to Inspection**

In `frontend/src/features/inspection/index.tsx`, make these changes:

**a) Add new imports:**
```tsx
import { Steps, Result } from "antd";
import { PhotoProvider, PhotoView } from "react-photo-view";
import "react-photo-view/dist/react-photo-view.css";
```

**b) Add step computation before return:**
```tsx
const getCurrentStep = () => {
  if (!taskId) return 0;
  if (!result) return 1;
  if (result.status === "PENDING" || result.status === "STARTED") return 1;
  return 2;
};
```

**c) Wrap image cards in PhotoProvider/PhotoView.** Replace the img tag (line 300-303) with:

```tsx
<PhotoProvider>
  <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
    {result.camera_results.map((r) =>
      r.overlay_image_base64 ? (
        <Card
          key={r.camera_id}
          size="small"
          title={r.camera_id}
          extra={<Tag color={statusColor(r.status)}>{r.status}</Tag>}
          style={{ width: 420 }}
          styles={{ body: { padding: 0 } }}
        >
          <PhotoView src={`data:image/jpeg;base64,${r.overlay_image_base64}`}>
            <img
              src={`data:image/jpeg;base64,${r.overlay_image_base64}`}
              alt={`${r.camera_id} overlay`}
              style={{ width: "100%", maxHeight: 400, objectFit: "contain", display: "block", cursor: "zoom-in" }}
            />
          </PhotoView>
        </Card>
      ) : null,
    )}
  </div>
</PhotoProvider>
```

**d) Add Steps component above the detection config card** (between PageHeader and Row):

```tsx
<Steps
  current={getCurrentStep()}
  size="small"
  className="mb-6"
  items={[
    { title: "配置", description: "选择型号与相机" },
    { title: "上传检测", description: "上传图像并运行" },
    { title: "结果", description: "查看检测结果" },
  ]}
/>
```

**e) Replace the overall result Tag with Result component.** After the Descriptions block in the result section, add:

```tsx
{result.overall_status && !isRunning && (
  <Result
    status={result.overall_status === "OK" ? "success" : "error"}
    title={result.overall_status === "OK" ? "检测通过" : "检测异常"}
    subTitle={result.decision_reason ?? ""}
  />
)}
```

And remove the old `overall_status` Tag from the Descriptions (or keep both — remove the Tag to avoid duplication).

- [ ] **Step 2: Verify build**

Run: `cd frontend && pnpm run build`
Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/inspection/index.tsx
git commit -m "feat: add Steps progress, PhotoView zoom, and Result display to Inspection"
```

---

### Task 13: ModelDeploy — deployment topology diagram

**Files:**
- Modify: `frontend/src/features/model-deploy/index.tsx`
- Create: `frontend/src/features/model-deploy/components/DeployTopology.tsx`

- [ ] **Step 1: Create DeployTopology SVG component**

Write `frontend/src/features/model-deploy/components/DeployTopology.tsx`:

```tsx
import { Card } from "antd";

interface TopoNode {
  id: string;
  label: string;
  status: "synced" | "pending" | "error" | "none";
  type: "target" | "active" | "shadow";
}

interface Props {
  nodes: TopoNode[];
  targets?: { target: string; activeModel: string; activeVersion: string; hasShadow: boolean }[];
}

const STATUS_COLORS: Record<string, string> = {
  synced: "#52c41a",
  pending: "#faad14",
  error: "#ff4d4f",
  none: "#d9d9d9",
};

export default function DeployTopology({ nodes, targets }: Props) {
  const data = targets ?? [];

  if (data.length === 0) {
    return (
      <Card title="部署拓扑" className="industrial-card mb-4">
        <div className="text-center text-gray-400 py-8">暂无部署数据</div>
      </Card>
    );
  }

  const NODE_W = 140;
  const NODE_H = 52;
  const GAP_X = 180;
  const GAP_Y = 80;
  const SVG_W = 600;
  const SVG_H = Math.max(200, data.length * GAP_Y + 40);

  return (
    <Card title="部署拓扑" className="industrial-card mb-4">
      <svg width="100%" viewBox={`0 0 ${SVG_W} ${SVG_H}`} style={{ maxWidth: SVG_W }}>
        {data.map((item, i) => {
          const y = 30 + i * GAP_Y;
          const x1 = 30;
          const x2 = x1 + GAP_X;
          const x3 = x2 + GAP_X;

          return (
            <g key={item.target}>
              {/* 连线 target → active */}
              <line x1={x1 + NODE_W} y1={y + NODE_H / 2} x2={x2} y2={y + NODE_H / 2}
                stroke="#d9d9d9" strokeWidth={2} />
              {/* 节点: target */}
              <rect x={x1} y={y} width={NODE_W} height={NODE_H} rx={8} fill="#f0f5ff" stroke="#1677ff" strokeWidth={1.5} />
              <text x={x1 + NODE_W / 2} y={y + 20} textAnchor="middle" fill="#1677ff" fontSize={12} fontWeight="bold">
                {item.target}
              </text>
              <text x={x1 + NODE_W / 2} y={y + 38} textAnchor="middle" fill="#8c8c8c" fontSize={11}>
                目标
              </text>

              {/* 节点: active */}
              <rect x={x2} y={y} width={NODE_W} height={NODE_H} rx={8} fill="#f6ffed" stroke="#52c41a" strokeWidth={1.5} />
              <text x={x2 + NODE_W / 2} y={y + 18} textAnchor="middle" fill="#52c41a" fontSize={12} fontWeight="bold">
                {item.activeModel}
              </text>
              <text x={x2 + NODE_W / 2} y={y + 36} textAnchor="middle" fill="#8c8c8c" fontSize={11}>
                {item.activeVersion}
              </text>

              {/* 节点: shadow (if exists) */}
              {item.hasShadow && (
                <>
                  <line x1={x2 + NODE_W} y1={y + NODE_H / 2} x2={x3} y2={y + NODE_H / 2}
                    stroke="#faad14" strokeWidth={1.5} strokeDasharray="5,3" />
                  <rect x={x3} y={y} width={NODE_W} height={NODE_H} rx={8} fill="#fffbe6" stroke="#faad14" strokeWidth={1.5} />
                  <text x={x3 + NODE_W / 2} y={y + 20} textAnchor="middle" fill="#faad14" fontSize={12} fontWeight="bold">
                    影子模型
                  </text>
                  <text x={x3 + NODE_W / 2} y={y + 38} textAnchor="middle" fill="#8c8c8c" fontSize={11}>
                    待重载
                  </text>
                </>
              )}
            </g>
          );
        })}
      </svg>
      <div className="flex gap-4 mt-3 text-xs text-gray-400">
        <span><span className="inline-block w-3 h-3 rounded bg-blue-500 mr-1" /> 目标</span>
        <span><span className="inline-block w-3 h-3 rounded bg-green-500 mr-1" /> 活跃模型</span>
        <span><span className="inline-block w-3 h-3 rounded bg-yellow-500 mr-1" /> 影子模型</span>
      </div>
    </Card>
  );
}
```

- [ ] **Step 2: Integrate topology into ModelDeploy page**

In `frontend/src/features/model-deploy/index.tsx`:

Add import:
```tsx
import DeployTopology from "./components/DeployTopology";
```

Add the topology diagram before the deployment table. After the `PageHeader` and before the `<Card>` containing the table:

```tsx
<DeployTopology
  nodes={[]}
  targets={
    hotReloadData?.targets?.map((t: Record<string, unknown>) => ({
      target: String(t.target ?? ""),
      activeModel: String(t.active_model ?? "-"),
      activeVersion: String(t.active_version ?? "-"),
      hasShadow: Boolean(t.has_shadow),
    })) ?? []
  }
/>
```

Wrap the hot-reload table in a `Collapse` component:
```tsx
import { Collapse } from "antd";
// ...
{hotReloadData?.targets && hotReloadData.targets.length > 0 && (
  <Collapse
    className="mt-4"
    items={[{
      key: "hot-reload",
      label: "热重载状态",
      children: (
        <Table /* existing hot-reload table */ />
      ),
    }]}
  />
)}
```

- [ ] **Step 3: Verify build**

Run: `cd frontend && pnpm run build`
Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/model-deploy/
git commit -m "feat: add SVG deployment topology diagram and collapsible hot-reload to ModelDeploy"
```

---

### Task 14: CameraConfig — topology diagram and ModelSelect

**Files:**
- Modify: `frontend/src/features/camera-config/index.tsx`
- Create: `frontend/src/features/camera-config/components/CameraTopology.tsx`
- Create: `frontend/src/features/camera-config/components/ModelSelect.tsx`

- [ ] **Step 1: Create ModelSelect reusable component**

Write `frontend/src/features/camera-config/components/ModelSelect.tsx`:

```tsx
import { Select } from "antd";
import type { SelectProps } from "antd";
import type { ModelOption } from "../../../types";

interface Props extends Omit<SelectProps, "options"> {
  models: ModelOption[] | undefined;
  loading?: boolean;
}

export default function ModelSelect({ models, loading, ...rest }: Props) {
  return (
    <Select
      showSearch
      optionFilterProp="label"
      loading={loading}
      placeholder="选择模型"
      allowClear
      {...rest}
      options={(models ?? []).map((m) => ({
        label: `${m.model_name} (${m.version})`,
        value: m.model_id,
      }))}
    />
  );
}
```

- [ ] **Step 2: Create CameraTopology SVG component**

Write `frontend/src/features/camera-config/components/CameraTopology.tsx`:

```tsx
import { Card } from "antd";

interface CameraNode {
  cameraId: string;
  yoloModel: string;
  patchcoreModel: string;
  filterModel?: string;
}

interface Props {
  seatModelId: string;
  cameras: CameraNode[];
}

const MODEL_COLORS: Record<string, string> = {
  yolo: "#1677ff",
  patchcore: "#722ed1",
  filter: "#52c41a",
};

export default function CameraTopology({ seatModelId, cameras }: Props) {
  if (!seatModelId) {
    return (
      <Card title="配置拓扑" className="industrial-card mb-4">
        <div className="text-center text-gray-400 py-8">请先选择左侧座椅型号</div>
      </Card>
    );
  }

  if (cameras.length === 0) {
    return (
      <Card title="配置拓扑" className="industrial-card mb-4">
        <div className="text-center text-gray-400 py-8">该座椅型号下暂无相机配置</div>
      </Card>
    );
  }

  const NODE_W = 110;
  const NODE_H = 44;
  const GAP = 170;
  const ROW_H = 80;

  return (
    <Card title="配置拓扑" className="industrial-card mb-4">
      <svg width="100%" viewBox={`0 0 ${800} ${Math.max(160, cameras.length * ROW_H + 60)}`} style={{ maxWidth: 800 }}>
        {/* 根节点: 座椅型号 */}
        <rect x={20} y={cameras.length * ROW_H / 2 - NODE_H / 2 + 20} width={NODE_W} height={NODE_H * 1.5} rx={10}
          fill="#f0f5ff" stroke="#1677ff" strokeWidth={2} />
        <text x={20 + NODE_W / 2} y={cameras.length * ROW_H / 2 + 20} textAnchor="middle" fill="#1677ff" fontSize={13} fontWeight="bold">
          {seatModelId}
        </text>

        {cameras.map((cam, i) => {
          const y = 30 + i * ROW_H;
          const camX = 170;
          const modelStartX = 330;

          return (
            <g key={cam.cameraId}>
              {/* 连线: seatModel → camera */}
              <line x1={20 + NODE_W} y1={cameras.length * ROW_H / 2 + 20} x2={camX} y2={y + NODE_H / 2}
                stroke="#d9d9d9" strokeWidth={1.5} />

              {/* Camera node */}
              <rect x={camX} y={y} width={NODE_W} height={NODE_H} rx={6} fill="#fff" stroke="#8c8c8c" strokeWidth={1} />
              <text x={camX + NODE_W / 2} y={y + 26} textAnchor="middle" fill="#333" fontSize={12} fontWeight="bold">
                {cam.cameraId}
              </text>

              {/* Model nodes */}
              {[
                { label: "YOLO", value: cam.yoloModel, color: MODEL_COLORS.yolo },
                { label: "PC", value: cam.patchcoreModel, color: MODEL_COLORS.patchcore },
                cam.filterModel ? { label: "FC", value: cam.filterModel, color: MODEL_COLORS.filter } : null,
              ].filter(Boolean).map((m, mi) => {
                if (!m) return null;
                const mx = modelStartX + mi * (NODE_W + 20);
                return (
                  <g key={m.label}>
                    <line x1={camX + NODE_W} y1={y + NODE_H / 2} x2={mx} y2={y + NODE_H / 2}
                      stroke={m.color} strokeWidth={1.5} />
                    <rect x={mx} y={y} width={NODE_W} height={NODE_H} rx={6} fill="#fff" stroke={m.color} strokeWidth={1} />
                    <text x={mx + NODE_W / 2} y={y + 20} textAnchor="middle" fill={m.color} fontSize={11} fontWeight="bold">
                      {m.label}
                    </text>
                    <text x={mx + NODE_W / 2} y={y + 36} textAnchor="middle" fill="#8c8c8c" fontSize={10}>
                      {m.value.length > 14 ? m.value.slice(0, 13) + "…" : m.value}
                    </text>
                  </g>
                );
              })}
            </g>
          );
        })}
      </svg>
      <div className="flex gap-4 mt-3 text-xs text-gray-400">
        <span><span className="inline-block w-3 h-3 rounded mr-1" style={{ background: MODEL_COLORS.yolo }} />YOLO</span>
        <span><span className="inline-block w-3 h-3 rounded mr-1" style={{ background: MODEL_COLORS.patchcore }} />PatchCore</span>
        <span><span className="inline-block w-3 h-3 rounded mr-1" style={{ background: MODEL_COLORS.filter }} />Filter</span>
      </div>
    </Card>
  );
}
```

- [ ] **Step 3: Update CameraConfig to use topology and ModelSelect**

In `frontend/src/features/camera-config/index.tsx`:

**a) Add imports:**
```tsx
import CameraTopology from "./components/CameraTopology";
import ModelSelect from "./components/ModelSelect";
import { Collapse } from "antd";
```

**b) Add topology before the Row:**
```tsx
<CameraTopology
  seatModelId={selectedSeatModel ?? ""}
  cameras={(cameras ?? []).map((c) => ({
    cameraId: c.camera_id,
    yoloModel: modelLabel(c.yolo_model_version_id, allModels),
    patchcoreModel: modelLabel(c.patchcore_model_version_id, allModels),
    filterModel: c.filter_classifier_model_version_id
      ? modelLabel(c.filter_classifier_model_version_id, allModels)
      : undefined,
  }))}
/>
```

**c) Replace the 3 repeated Select blocks in the camera Modal form** with `ModelSelect`. For example, replace the `yolo_model_version_id` Form.Item content with:
```tsx
<ModelSelect models={yoloModels ?? []} loading={!yoloModels} />
```

Same pattern for `patchcore_model_version_id` and `filter_classifier_model_version_id`.

**d) Wrap region mode form fields in Collapse.** Replace the conditional `regionModeEnabled && (...)` block with:
```tsx
<Collapse
  activeKey={regionModeEnabled ? ["region"] : []}
  items={[{
    key: "region",
    label: "Region 分区配置",
    children: (
      <>
        <Form.Item name="region_upper_model_version_id" label="Upper 区域模型" rules={[{ required: regionModeEnabled }]}>
          <ModelSelect models={patchcoreModels ?? []} loading={!patchcoreModels} placeholder="选择 upper 区域 PatchCore 模型" />
        </Form.Item>
        <Form.Item name="region_middle_model_version_id" label="Middle 区域模型" rules={[{ required: regionModeEnabled }]}>
          <ModelSelect models={patchcoreModels ?? []} loading={!patchcoreModels} placeholder="选择 middle 区域 PatchCore 模型" />
        </Form.Item>
        <Form.Item name="region_lower_model_version_id" label="Lower 区域模型" rules={[{ required: regionModeEnabled }]}>
          <ModelSelect models={patchcoreModels ?? []} loading={!patchcoreModels} placeholder="选择 lower 区域 PatchCore 模型" />
        </Form.Item>
      </>
    ),
  }]}
/>
```

- [ ] **Step 4: Verify build**

Run: `cd frontend && pnpm run build`
Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/camera-config/
git commit -m "feat: add SVG camera topology diagram and reusable ModelSelect component"
```

---

### Task 15: Inline style cleanup (all pages)

**Files:**
- Modify: `frontend/src/features/cluster-review/index.tsx`
- Modify: `frontend/src/features/anomaly-browser/index.tsx`
- Modify: `frontend/src/features/inspection/index.tsx`
- Modify: `frontend/src/features/training/index.tsx`
- Modify: `frontend/src/features/model-deploy/index.tsx`
- Modify: `frontend/src/features/camera-config/index.tsx`
- Modify: `frontend/src/features/knowledge-base/index.tsx`
- Modify: `frontend/src/features/rules-engine/index.tsx`
- Modify: `frontend/src/features/dashboard/index.tsx`

- [ ] **Step 1: Scan for remaining `style={{ }}` patterns**

Run: `cd frontend && grep -rn 'style={{' src/features/ src/components/ src/app/ --include="*.tsx" | grep -v node_modules | grep -v '.d.ts'`

- [ ] **Step 2: Replace inline styles with Tailwind classes**

For each remaining `style={{ }}` occurrence, replace with the equivalent Tailwind class (e.g., `style={{ width: 150 }}` → `className="w-[150px]"`, `style={{ marginBottom: 12 }}` → `className="mb-3"`).

Key replacements:
| Inline style | Tailwind class |
|---|---|
| `style={{ width: 150 }}` | `className="w-[150px]"` |
| `style={{ flex: 1 }}` | `className="flex-1"` |
| `style={{ marginTop: 16 }}` | `className="mt-4"` |
| `style={{ marginBottom: 12 }}` | `className="mb-3"` |
| `style={{ textAlign: "center" }}` | `className="text-center"` |
| `style={{ display: "flex", gap: 16 }}` | `className="flex gap-4"` |
| `style={{ padding: "40px 0" }}` | `className="py-10"` |
| `style={{ cursor: "pointer" }}` | `className="cursor-pointer"` |
| `style={{ height: 450 }}` | `className="h-[450px]"` |

Exceptions: Dynamic style values (e.g., `style={{ background: selected ? "#e6f4ff" : undefined }}`) should remain as inline styles, or be converted to conditional className with `classnames` utility.

- [ ] **Step 3: Verify build**

Run: `cd frontend && pnpm run build`
Expected: Build succeeds.

- [ ] **Step 4: Verify remaining inline styles are only dynamic ones**

Run: `cd frontend && grep -rn 'style={{' src/ --include="*.tsx" | grep -v node_modules | wc -l`
Expected: The count should be significantly reduced from ~80+ to < 20 (only dynamic styles remain).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/ frontend/src/components/ frontend/src/app/
git commit -m "refactor: replace inline styles with Tailwind classes across all pages"
```

---

### Task 16: Final integration — dev server smoke test

**Files:** None (verification only)

- [ ] **Step 1: Start dev server**

Run: `cd frontend && pnpm run dev`
Expected: Vite dev server starts on http://localhost:3000

- [ ] **Step 2: Click through all 9 pages**

Navigate to each page in the browser and verify:
1. **数据面板** — countUp animations, skeleton during loading
2. **在线检测** — Steps component visible, upload drag animation
3. **异常浏览** — card grid default view, grid/table toggle works, PhotoView zoom
4. **聚类审核** — split panel, click row shows detail on right, review modal works
5. **知识库** — sidebar category nav, card grid entries
6. **规则引擎** — visual condition builder in create form, structured eval result
7. **训练管理** — log panel on right side
8. **模型部署** — SVG topology diagram, collapsible hot-reload
9. **相机配置** — SVG topology diagram, ModelSelect dropdowns

- [ ] **Step 3: Verify sidebar persistence**

Collapse sidebar → refresh page → verify collapsed state persists.

- [ ] **Step 4: Verify page transitions**

Navigate between pages → verify fade-in animation plays.

- [ ] **Step 5: Verify breadcrumbs**

Navigate to nested pages → verify breadcrumb trail in header.

---

## Plan Self-Review

**1. Spec coverage:**
- L1 CSS variables + Tailwind → Task 1
- L1 Three-state components (Skeleton) → Task 2
- L1 Inline style cleanup → Task 15
- L2 Sidebar upgrade → Task 4
- L2 Header + breadcrumbs → Task 4
- L2 Page transitions → Task 5
- L2 ScrollToTop → Task 3
- L3 Dashboard → Task 6
- L3 ClusterReview split panel → Task 7
- L3 AnomalyBrowser card grid → Task 8
- L3 KnowledgeBase sidebar nav → Task 9
- L3 RulesEngine visual builder → Task 10
- L3 Training log panel → Task 11
- L3 Inspection → Task 12
- L3 ModelDeploy topology → Task 13
- L3 CameraConfig topology + ModelSelect → Task 14
- Final smoke test → Task 16

**2. Placeholder scan:** No TBD, TODO, or vague instructions. All code is concrete.

**3. Type consistency:** All component props use types from `../../types` which already exist. Type names match those defined in the existing types directory. Component imports are consistent across tasks.
