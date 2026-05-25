import { Space, Tag, Button, Typography, Popconfirm } from "antd";
import { EyeOutlined, BookOutlined, DeleteOutlined, ClusterOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import type { ColumnsType } from "antd/es/table";
import type { KnowledgeEntry } from "../../../types";
import { CATEGORY_COLOR_MAP } from "../../../lib/constants";

const { Text } = Typography;

interface Props {
  onViewDetail: (entry: KnowledgeEntry) => void;
  onGenerateRule: (entry: KnowledgeEntry) => void;
  onDelete: (id: string) => void;
}

export function useKnowledgeColumns({ onViewDetail, onGenerateRule, onDelete }: Props): ColumnsType<KnowledgeEntry> {
  // eslint-disable-next-line react-hooks/rules-of-hooks
  const navigate = useNavigate();

  return [
    {
      title: "标题",
      dataIndex: "title",
      key: "title",
      render: (t: string) => <Text strong>{t}</Text>,
    },
    {
      title: "类别",
      dataIndex: "category",
      key: "category",
      width: 120,
      render: (c: string) => (
        <Tag color={CATEGORY_COLOR_MAP[c] || "default"}>{c.replace(/_/g, " ")}</Tag>
      ),
    },
    {
      title: "缺陷类型",
      dataIndex: "defect_type",
      key: "defect_type",
      width: 110,
      render: (d: string | null) => <Tag color="purple">{d || "-"}</Tag>,
    },
    {
      title: "动作",
      dataIndex: "action",
      key: "action",
      width: 80,
      render: (a: string) => {
        const colors: Record<string, string> = {
          ignore: "green",
          NG: "red",
          review_required: "orange",
        };
        return <Tag color={colors[a] || "default"}>{a}</Tag>;
      },
    },
    {
      title: "聚类",
      dataIndex: "cluster_id",
      key: "cluster_id",
      width: 120,
      render: (c: string | null) =>
        c ? (
          <Button
            type="link"
            size="small"
            icon={<ClusterOutlined />}
            onClick={() => navigate(`/clusters?cluster_id=${c}`)}
          >
            {c.slice(0, 10)}...
          </Button>
        ) : (
          <Text type="secondary">-</Text>
        ),
    },
    {
      title: "相机",
      dataIndex: "camera_ids",
      key: "camera_ids",
      width: 140,
      render: (ids: string[]) =>
        ids.length > 0 ? (
          <Space size={4} wrap>
            {ids.map((id) => (
              <Tag key={id} className="text-xs">{id}</Tag>
            ))}
          </Space>
        ) : (
          <Text type="secondary">全部</Text>
        ),
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      key: "created_at",
      width: 170,
      render: (d: string) => new Date(d).toLocaleString(),
    },
    {
      title: "操作",
      key: "actions",
      width: 200,
      render: (_: unknown, record: KnowledgeEntry) => (
        <Space>
          <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => onViewDetail(record)}>
            查看
          </Button>
          <Button type="link" size="small" icon={<BookOutlined />} onClick={() => onGenerateRule(record)}>
            生成规则
          </Button>
          <Popconfirm title="确定要删除此条目吗？" onConfirm={() => onDelete(record.knowledge_id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];
}
