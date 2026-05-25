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
      title: "聚类",
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
      title: "样本数",
      dataIndex: "sample_count",
      key: "sample_count",
      sorter: (a, b) => a.sample_count - b.sample_count,
    },
    {
      title: "可能类型",
      dataIndex: "possible_type",
      key: "possible_type",
      render: (t: string | null) => <Tag color="blue">{t || "未知"}</Tag>,
    },
    {
      title: "审核状态",
      dataIndex: "review_status",
      key: "review_status",
      render: (s: string | null) => (
        <Tag color={STATUS_COLOR_MAP[s || ""] || "orange"}>{s || "待审核"}</Tag>
      ),
    },
    {
      title: "缺陷类型",
      dataIndex: "defect_type",
      key: "defect_type",
      render: (t: string | null) => <Tag color="purple">{t || "-"}</Tag>,
    },
    {
      title: "VLM",
      key: "vlm",
      render: (_: unknown, record: ClusterSummary) =>
        record.vlm_analyzed_at ? (
          <Space size={4}>
            <Tag color={record.vlm_is_false_alarm ? "green" : "orange"}>
              {record.vlm_anomaly_type || "已分析"}
            </Tag>
          </Space>
        ) : (
          <Text type="secondary" className="text-xs">-</Text>
        ),
    },
    {
      title: "操作",
      key: "actions",
      width: 320,
      render: (_: unknown, record: ClusterSummary) => (
        <Space>
          <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => onViewDetail(record.cluster_id)}>
            详情
          </Button>
          {record.status === "pending_review" && (
            <>
              <Button
                type="primary"
                size="small"
                icon={<CheckOutlined />}
                onClick={() => onReview(record, "confirm_defect")}
              >
                确认缺陷
              </Button>
              <Button
                danger
                size="small"
                icon={<CloseOutlined />}
                onClick={() => onReview(record, "mark_false_alarm")}
              >
                标记误报
              </Button>
            </>
          )}
        </Space>
      ),
    },
  ];
}
