import { Space, Tag, Button, Typography, Popconfirm } from "antd";
import { RetweetOutlined, DeleteOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import type { AnomalyRecord } from "../../../types";
import { ANOMALY_STATUS_COLOR_MAP } from "../../../lib/constants";

const { Text } = Typography;

interface Props {
  onViewDetail: (id: string) => void;
  onReprocess: (id: string) => void;
  onDelete: (id: string) => void;
}

export function useAnomalyColumns({ onViewDetail, onReprocess, onDelete }: Props): ColumnsType<AnomalyRecord> {
  return [
    {
      title: "ID",
      dataIndex: "anomaly_id",
      key: "anomaly_id",
      render: (id: string) => <Text code>{id.slice(0, 12)}...</Text>,
    },
    { title: "相机", dataIndex: "camera_id", key: "camera_id" },
    { title: "来源", dataIndex: "source", key: "source", render: (s: string) => <Tag>{s}</Tag> },
    {
      title: "分数",
      dataIndex: "anomaly_score",
      key: "anomaly_score",
      render: (s: number | null) => (s !== null ? s.toFixed(3) : "-"),
    },
    { title: "日期", dataIndex: "date_folder", key: "date_folder" },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      render: (s: string) => <Tag color={ANOMALY_STATUS_COLOR_MAP[s] || "default"}>{s}</Tag>,
    },
    {
      title: "操作",
      key: "actions",
      render: (_: unknown, record: AnomalyRecord) => (
        <Space>
          <Button type="link" size="small" onClick={() => onViewDetail(record.anomaly_id)}>
            详情
          </Button>
          <Button
            type="link"
            size="small"
            icon={<RetweetOutlined />}
            onClick={() => onReprocess(record.anomaly_id)}
          >
            重新处理
          </Button>
          <Popconfirm
            title="确定要删除此异常吗？"
            description="数据将被软删除并从流程中排除。"
            onConfirm={() => onDelete(record.anomaly_id)}
            okText="删除"
            cancelText="取消"
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];
}
