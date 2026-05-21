import { Space, Tag, Button, Typography, Popconfirm } from "antd";
import { EyeOutlined, BookOutlined, DeleteOutlined } from "@ant-design/icons";
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
  return [
    {
      title: "Title",
      dataIndex: "title",
      key: "title",
      render: (t: string) => <Text strong>{t}</Text>,
    },
    {
      title: "Category",
      dataIndex: "category",
      key: "category",
      width: 120,
      render: (c: string) => (
        <Tag color={CATEGORY_COLOR_MAP[c] || "default"}>{c.replace(/_/g, " ")}</Tag>
      ),
    },
    {
      title: "Defect Type",
      dataIndex: "defect_type",
      key: "defect_type",
      width: 110,
      render: (d: string | null) => <Tag color="purple">{d || "-"}</Tag>,
    },
    {
      title: "Action",
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
      title: "Cluster",
      dataIndex: "cluster_id",
      key: "cluster_id",
      width: 120,
      render: (c: string | null) =>
        c ? <Text code>{c.slice(0, 10)}...</Text> : <Text type="secondary">-</Text>,
    },
    {
      title: "Cameras",
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
          <Text type="secondary">all</Text>
        ),
    },
    {
      title: "Created",
      dataIndex: "created_at",
      key: "created_at",
      width: 170,
      render: (d: string) => new Date(d).toLocaleString(),
    },
    {
      title: "Actions",
      key: "actions",
      width: 200,
      render: (_: unknown, record: KnowledgeEntry) => (
        <Space>
          <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => onViewDetail(record)}>
            View
          </Button>
          <Button type="link" size="small" icon={<BookOutlined />} onClick={() => onGenerateRule(record)}>
            Gen Rule
          </Button>
          <Popconfirm title="Delete this entry?" onConfirm={() => onDelete(record.knowledge_id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              Delete
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];
}
