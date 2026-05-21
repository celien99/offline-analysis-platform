import { List } from "antd";
import type { ClusterSummary } from "../types";
import ClusterCard from "./ClusterCard";

interface Props {
  clusters: ClusterSummary[];
  loading?: boolean;
  onClusterClick?: (clusterId: string) => void;
}

export default function ClusterList({
  clusters,
  loading,
  onClusterClick,
}: Props) {
  return (
    <List
      loading={loading}
      dataSource={clusters}
      renderItem={(cluster) => (
        <ClusterCard cluster={cluster} onClick={onClusterClick} />
      )}
    />
  );
}
