import { Routes, Route, Navigate } from "react-router-dom";
import { Layout, Menu } from "antd";
import {
  DashboardOutlined,
  ClusterOutlined,
  BugOutlined,
  BookOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { useNavigate, useLocation } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import ClusterReview from "./pages/ClusterReview";
import AnomalyBrowser from "./pages/AnomalyBrowser";
import KnowledgeBase from "./pages/KnowledgeBase";
import RulesManagement from "./pages/RulesManagement";

const { Sider, Content, Header } = Layout;

const menuItems = [
  { key: "/", icon: <DashboardOutlined />, label: "Dashboard" },
  { key: "/clusters", icon: <ClusterOutlined />, label: "Cluster Review" },
  { key: "/anomalies", icon: <BugOutlined />, label: "Anomaly Browser" },
  { key: "/knowledge", icon: <BookOutlined />, label: "Knowledge Base" },
  { key: "/rules", icon: <ThunderboltOutlined />, label: "Rules Engine" },
];

export default function App() {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider collapsible>
        <div
          style={{
            height: 48,
            margin: 16,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#fff",
            fontWeight: "bold",
            fontSize: 16,
          }}
        >
          AI Evolution Platform
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            background: "#fff",
            padding: "0 24px",
            fontSize: 18,
            fontWeight: 600,
          }}
        >
          Industrial Defect Detection — Offline Analysis Platform
        </Header>
        <Content style={{ margin: 24, minHeight: 280 }}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/clusters" element={<ClusterReview />} />
            <Route path="/anomalies" element={<AnomalyBrowser />} />
            <Route path="/knowledge" element={<KnowledgeBase />} />
            <Route path="/rules" element={<RulesManagement />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
}
