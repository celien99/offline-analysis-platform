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
  const items: { title: ReactNode }[] = [{ title: <Link to="/">数据面板</Link> }];

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
          className="bg-transparent mt-1"
        />
      </Sider>
      <Layout>
        <Header
          className="bg-white px-6 flex items-center justify-between sticky top-0 z-10 border-b border-gray-100"
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
