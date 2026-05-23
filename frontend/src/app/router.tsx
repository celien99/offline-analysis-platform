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

function LazyFallback() {
  return (
    <div className="flex items-center justify-center py-20">
      <Spin size="large" />
    </div>
  );
}

export default function AppRouter() {
  return (
    <Suspense fallback={<LazyFallback />}>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/inspection" element={<Inspection />} />
        <Route path="/anomalies" element={<AnomalyBrowser />} />
        <Route path="/clusters" element={<ClusterReview />} />

        <Route path="/knowledge" element={<KnowledgeBase />} />
        <Route path="/rules" element={<RulesManagement />} />
        <Route path="/training" element={<Training />} />
        <Route path="/deploy" element={<ModelDeploy />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
