import type { ReactNode } from "react";
import { Layout, Menu } from "antd";
import {
  DashboardOutlined,
  ClusterOutlined,
  BugOutlined,

  BookOutlined,
  ThunderboltOutlined,
  ExperimentOutlined,
  RocketOutlined,
  ScanOutlined,
} from "@ant-design/icons";
import { useNavigate, useLocation } from "react-router-dom";

const { Sider, Content, Header } = Layout;

const menuItems = [
  { key: "/", icon: <DashboardOutlined />, label: "数据面板" },
  { key: "/inspection", icon: <ScanOutlined />, label: "在线检测" },
  { key: "/anomalies", icon: <BugOutlined />, label: "异常浏览" },

  { key: "/clusters", icon: <ClusterOutlined />, label: "聚类审核" },

  { key: "/knowledge", icon: <BookOutlined />, label: "知识库" },
  { key: "/rules", icon: <ThunderboltOutlined />, label: "规则引擎" },
  { key: "/training", icon: <ExperimentOutlined />, label: "训练管理" },
  { key: "/deploy", icon: <RocketOutlined />, label: "模型部署" },
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
          AI 进化平台
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
        <Header className="bg-white px-6 text-lg font-semibold flex items-center">
          工业缺陷检测 — 离线分析平台
        </Header>
        <Content className="m-6 min-h-[280px]">{children}</Content>
      </Layout>
    </Layout>
  );
}
