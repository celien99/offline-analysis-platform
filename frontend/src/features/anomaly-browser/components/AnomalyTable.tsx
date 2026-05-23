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
    { title: "Camera", dataIndex: "camera_id", key: "camera_id" },
    { title: "Source", dataIndex: "source", key: "source", render: (s: string) => <Tag>{s}</Tag> },
    {
      title: "Score",
      dataIndex: "anomaly_score",
      key: "anomaly_score",
      render: (s: number | null) => (s !== null ? s.toFixed(3) : "-"),
    },
    { title: "Date", dataIndex: "date_folder", key: "date_folder" },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      render: (s: string) => <Tag color={ANOMALY_STATUS_COLOR_MAP[s] || "default"}>{s}</Tag>,
    },
    {
      title: "Actions",
      key: "actions",
      render: (_: unknown, record: AnomalyRecord) => (
        <Space>
          <Button type="link" size="small" onClick={() => onViewDetail(record.anomaly_id)}>
            Detail
          </Button>
          <Button
            type="link"
            size="small"
            icon={<RetweetOutlined />}
            onClick={() => onReprocess(record.anomaly_id)}
          >
            Reprocess
          </Button>
          <Popconfirm
            title="Delete this anomaly?"
            description="The data will be soft-deleted and excluded from pipeline."
            onConfirm={() => onDelete(record.anomaly_id)}
            okText="Delete"
            cancelText="Cancel"
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              Delete
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];
}
