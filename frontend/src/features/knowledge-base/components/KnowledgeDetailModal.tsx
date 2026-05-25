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
      title="知识条目详情"
      open={open}
      onCancel={onClose}
      footer={
        <Space>
          <Button onClick={() => onGenerateRule(entry)}>生成规则</Button>
          <Popconfirm
            title="确定要删除此条目吗？"
            onConfirm={() => {
              onDelete(entry.knowledge_id);
              onClose();
            }}
          >
            <Button danger>删除</Button>
          </Popconfirm>
          <Button onClick={onClose}>关闭</Button>
        </Space>
      }
      width={700}
    >
      <Descriptions column={2} bordered size="small">
        <Descriptions.Item label="标题" span={2}>{entry.title}</Descriptions.Item>
        <Descriptions.Item label="类别">
          <Tag color={CATEGORY_COLOR_MAP[entry.category]}>
            {entry.category.replace(/_/g, " ")}
          </Tag>
        </Descriptions.Item>
        <Descriptions.Item label="动作">
          <Tag color={entry.action === "ignore" ? "green" : "red"}>{entry.action}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="缺陷类型">{entry.defect_type || "-"}</Descriptions.Item>
        <Descriptions.Item label="聚类">{entry.cluster_id || "-"}</Descriptions.Item>
        <Descriptions.Item label="相机" span={2}>
          {entry.camera_ids.length > 0 ? entry.camera_ids.join(", ") : "所有相机"}
        </Descriptions.Item>
        <Descriptions.Item label="描述" span={2}>
          <Paragraph>{entry.description || "无描述"}</Paragraph>
        </Descriptions.Item>
        <Descriptions.Item label="创建时间" span={2}>
          {new Date(entry.created_at).toLocaleString()}
        </Descriptions.Item>
      </Descriptions>
    </Modal>
  );
}
