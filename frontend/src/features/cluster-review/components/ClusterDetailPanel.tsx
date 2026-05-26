import { Empty, Descriptions, Tag, Button, Space, Card, Typography } from "antd";
import { CheckCircleOutlined, CloseCircleOutlined } from "@ant-design/icons";
import type { ClusterSummary } from "../../../types";
import { STATUS_COLOR_MAP } from "../../../lib/constants";

const { Text } = Typography;
const { Item } = Descriptions;

interface Props {
  cluster: ClusterSummary | null;
  onReview: (cluster: ClusterSummary, action: "confirm_defect" | "mark_false_alarm") => void;
}

export default function ClusterDetailPanel({ cluster, onReview }: Props) {
  if (!cluster) {
    return (
      <Card className="industrial-card h-full flex items-center justify-center min-h-[400px]">
        <Empty description="选择左侧聚类查看详情" />
      </Card>
    );
  }

  const sampleImages = (cluster as unknown as Record<string, unknown>).sample_image_urls as string[] | undefined;
  const description = (cluster as unknown as Record<string, unknown>).description as string | undefined;

  return (
    <Card
      className="industrial-card"
      title={
        <Space>
          <Text strong>{cluster.name}</Text>
          <Tag color={STATUS_COLOR_MAP[cluster.review_status ?? ""] || "default"}>
            {cluster.review_status}
          </Tag>
        </Space>
      }
      extra={
        <Space>
          <Button
            type="primary"
            danger
            icon={<CheckCircleOutlined />}
            onClick={() => onReview(cluster, "confirm_defect")}
          >
            确认为缺陷
          </Button>
          <Button
            icon={<CloseCircleOutlined />}
            onClick={() => onReview(cluster, "mark_false_alarm")}
          >
            标记误报
          </Button>
        </Space>
      }
    >
      <Descriptions column={2} size="small" bordered className="mb-4">
        <Item label="样本数量">{cluster.sample_count}</Item>
        <Item label="可能类型">{cluster.possible_type ?? "-"}</Item>
        <Item label="缺陷类型">{cluster.defect_type ?? "-"}</Item>
        <Item label="相机ID">{cluster.camera_id ?? "-"}</Item>
        <Item label="区域ID" span={2}>{cluster.region_id ?? "-"}</Item>
      </Descriptions>

      {sampleImages && sampleImages.length > 0 && (
        <>
          <Text strong className="block mb-2">样本图像</Text>
          <div className="flex gap-2 overflow-x-auto pb-2">
            {sampleImages.map((url, i) => (
              <img
                key={i}
                src={url}
                alt={`sample-${i}`}
                className="w-24 h-24 object-cover rounded cursor-pointer hover:opacity-80 transition-opacity"
              />
            ))}
          </div>
        </>
      )}

      {description && (
        <>
          <Text strong className="block mt-4 mb-2">描述</Text>
          <Text type="secondary">{description}</Text>
        </>
      )}
    </Card>
  );
}
