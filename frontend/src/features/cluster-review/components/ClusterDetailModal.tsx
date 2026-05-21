import { Modal, Descriptions } from "antd";
import type { ClusterDetail } from "../../../types";

interface Props {
  cluster: ClusterDetail | null;
  open: boolean;
  onClose: () => void;
}

export default function ClusterDetailModal({ cluster, open, onClose }: Props) {
  return (
    <Modal title="Cluster Detail" open={open} onCancel={onClose} footer={null} width={800}>
      {cluster && (
        <Descriptions column={2} bordered size="small">
          <Descriptions.Item label="Cluster ID">{cluster.cluster_id}</Descriptions.Item>
          <Descriptions.Item label="Samples">{cluster.sample_count}</Descriptions.Item>
          <Descriptions.Item label="HDBSCAN Label">{cluster.hdbscan_label}</Descriptions.Item>
          <Descriptions.Item label="Probability">
            {cluster.hdbscan_probability?.toFixed(3) ?? "-"}
          </Descriptions.Item>
          <Descriptions.Item label="Status">{cluster.status}</Descriptions.Item>
          <Descriptions.Item label="Defect Type">{cluster.defect_type || "-"}</Descriptions.Item>
        </Descriptions>
      )}
    </Modal>
  );
}
