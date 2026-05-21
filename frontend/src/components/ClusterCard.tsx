import { Card, Tag, Typography } from "antd";
import type { ClusterSummary } from "../types";

const { Text } = Typography;

interface Props {
  cluster: ClusterSummary;
  onClick?: (clusterId: string) => void;
}

export default function ClusterCard({ cluster, onClick }: Props) {
  return (
    <Card
      hoverable
      size="small"
      style={{ marginBottom: 12 }}
      onClick={() => onClick?.(cluster.cluster_id)}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Text strong>
          {cluster.name || `Cluster #${cluster.cluster_id.slice(0, 8)}`}
        </Text>
        <Tag color={cluster.review_status === "real_defect" ? "red" : "green"}>
          {cluster.review_status || "pending"}
        </Tag>
      </div>
      <div style={{ marginTop: 8 }}>
        <Text type="secondary">
          {cluster.sample_count} samples
          {cluster.possible_type && ` · ${cluster.possible_type}`}
        </Text>
      </div>
    </Card>
  );
}
