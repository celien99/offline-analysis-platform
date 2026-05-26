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
