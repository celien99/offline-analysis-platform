import { Modal, Descriptions, Tag, Button, Space, Popconfirm, Typography } from "antd";
import type { KnowledgeEntry } from "../../../types";
import { CATEGORY_COLOR_MAP } from "../../../lib/constants";

const { Paragraph } = Typography;

interface Props {
  entry: KnowledgeEntry | null;
  open: boolean;
  onClose: () => void;
  onGenerateRule: (entry: KnowledgeEntry) => void;
  onDelete: (id: string) => void;
}

export default function KnowledgeDetailModal({ entry, open, onClose, onGenerateRule, onDelete }: Props) {
  if (!entry) return null;

  return (
    <Modal
      title="Knowledge Entry Detail"
      open={open}
      onCancel={onClose}
      footer={
        <Space>
          <Button onClick={() => onGenerateRule(entry)}>Generate Rule</Button>
          <Popconfirm
            title="Delete this entry?"
            onConfirm={() => {
              onDelete(entry.knowledge_id);
              onClose();
            }}
          >
            <Button danger>Delete</Button>
          </Popconfirm>
          <Button onClick={onClose}>Close</Button>
        </Space>
      }
      width={700}
    >
      <Descriptions column={2} bordered size="small">
        <Descriptions.Item label="Title" span={2}>{entry.title}</Descriptions.Item>
        <Descriptions.Item label="Category">
          <Tag color={CATEGORY_COLOR_MAP[entry.category]}>
            {entry.category.replace(/_/g, " ")}
          </Tag>
        </Descriptions.Item>
        <Descriptions.Item label="Action">
          <Tag color={entry.action === "ignore" ? "green" : "red"}>{entry.action}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="Defect Type">{entry.defect_type || "-"}</Descriptions.Item>
        <Descriptions.Item label="Cluster">{entry.cluster_id || "-"}</Descriptions.Item>
        <Descriptions.Item label="Cameras" span={2}>
          {entry.camera_ids.length > 0 ? entry.camera_ids.join(", ") : "All cameras"}
        </Descriptions.Item>
        <Descriptions.Item label="Description" span={2}>
          <Paragraph>{entry.description || "No description"}</Paragraph>
        </Descriptions.Item>
        <Descriptions.Item label="Created" span={2}>
          {new Date(entry.created_at).toLocaleString()}
        </Descriptions.Item>
      </Descriptions>
    </Modal>
  );
}
