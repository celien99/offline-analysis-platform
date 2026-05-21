import { Space, Badge, Tag, Button, Typography } from "antd";
import { EyeOutlined, CheckOutlined, CloseOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import type { ClusterSummary } from "../../../types";
import { STATUS_COLOR_MAP } from "../../../lib/constants";

const { Text } = Typography;

interface Props {
  clusters: ClusterSummary[];
  onViewDetail: (id: string) => void;
  onReview: (cluster: ClusterSummary, action: "confirm_defect" | "mark_false_alarm") => void;
}

export function useClusterColumns({ onViewDetail, onReview }: Props): ColumnsType<ClusterSummary> {
  return [
    {
      title: "Cluster",
      dataIndex: "name",
      key: "name",
      render: (_: string, record: ClusterSummary) => (
        <Space>
          <Badge
            status={
              record.review_status === "real_defect"
                ? "error"
                : record.review_status === "false_alarm"
                  ? "success"
                  : "processing"
            }
          />
          <Text strong>{record.name || `Cluster #${record.cluster_id.slice(0, 8)}`}</Text>
        </Space>
      ),
    },
    {
      title: "Samples",
      dataIndex: "sample_count",
      key: "sample_count",
      sorter: (a, b) => a.sample_count - b.sample_count,
    },
    {
      title: "Possible Type",
      dataIndex: "possible_type",
      key: "possible_type",
      render: (t: string | null) => <Tag color="blue">{t || "unknown"}</Tag>,
    },
    {
      title: "Review Status",
      dataIndex: "review_status",
      key: "review_status",
      render: (s: string | null) => (
        <Tag color={STATUS_COLOR_MAP[s || ""] || "orange"}>{s || "pending"}</Tag>
      ),
    },
    {
      title: "Defect Type",
      dataIndex: "defect_type",
      key: "defect_type",
      render: (t: string | null) => <Tag color="purple">{t || "-"}</Tag>,
    },
    {
      title: "Actions",
      key: "actions",
      width: 320,
      render: (_: unknown, record: ClusterSummary) => (
        <Space>
          <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => onViewDetail(record.cluster_id)}>
            Detail
          </Button>
          {record.status === "pending_review" && (
            <>
              <Button
                type="primary"
                size="small"
                icon={<CheckOutlined />}
                onClick={() => onReview(record, "confirm_defect")}
              >
                Confirm
              </Button>
              <Button
                danger
                size="small"
                icon={<CloseOutlined />}
                onClick={() => onReview(record, "mark_false_alarm")}
              >
                False Alarm
              </Button>
            </>
          )}
        </Space>
      ),
    },
  ];
}
