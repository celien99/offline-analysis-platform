import type { ReactNode } from "react";
import { Layout, Menu } from "antd";
import {
  DashboardOutlined,
  ClusterOutlined,
  BugOutlined,
  UploadOutlined,
  BookOutlined,
  ThunderboltOutlined,
  ExperimentOutlined,
  RocketOutlined,
  ScanOutlined,
} from "@ant-design/icons";
import { useNavigate, useLocation } from "react-router-dom";

const { Sider, Content, Header } = Layout;

const menuItems = [
  { key: "/", icon: <DashboardOutlined />, label: "Dashboard" },
  { key: "/clusters", icon: <ClusterOutlined />, label: "Cluster Review" },
  { key: "/anomalies", icon: <BugOutlined />, label: "Anomaly Browser" },
  { key: "/upload", icon: <UploadOutlined />, label: "Upload" },
  { key: "/knowledge", icon: <BookOutlined />, label: "Knowledge Base" },
  { key: "/rules", icon: <ThunderboltOutlined />, label: "Rules Engine" },
  { key: "/training", icon: <ExperimentOutlined />, label: "Training" },
  { key: "/deploy", icon: <RocketOutlined />, label: "Deploy" },
  { key: "/inspection", icon: <ScanOutlined />, label: "Inspection" },
];

interface Props {
  children: ReactNode;
}

export default function AppLayout({ children }: Props) {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <Layout className="min-h-screen">
      <Sider collapsible>
        <div className="h-12 mx-4 flex items-center justify-center text-white font-bold text-base">
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
        <Header className="bg-white px-6 text-lg font-semibold">
          Industrial Defect Detection — Offline Analysis Platform
        </Header>
        <Content className="m-6 min-h-[280px]">{children}</Content>
      </Layout>
    </Layout>
  );
}
