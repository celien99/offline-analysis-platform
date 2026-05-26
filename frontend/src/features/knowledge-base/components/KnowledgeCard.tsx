import { Card, Tag, Typography, Button, Space, Popconfirm } from "antd";
import { DeleteOutlined, ThunderboltOutlined } from "@ant-design/icons";
import type { KnowledgeEntry } from "../../../types";
import { CATEGORY_COLOR_MAP } from "../../../lib/constants";
import dayjs from "dayjs";

const { Text, Paragraph } = Typography;

interface Props {
  entry: KnowledgeEntry;
  onViewDetail: (entry: KnowledgeEntry) => void;
  onGenerateRule: (entry: KnowledgeEntry) => void;
  onDelete: (id: string) => void;
}

export default function KnowledgeCard({ entry, onViewDetail, onGenerateRule, onDelete }: Props) {
  return (
    <Card
      hoverable
      className="industrial-card"
      onClick={() => onViewDetail(entry)}
    >
      <div className="flex items-start justify-between mb-2">
        <Text strong className="text-base">{entry.title ?? entry.knowledge_id}</Text>
        <Space>
          <Button
            size="small"
            type="text"
            icon={<ThunderboltOutlined />}
            onClick={(e) => {
              e.stopPropagation();
              onGenerateRule(entry);
            }}
          />
          <Popconfirm
            title="确定删除此条目？"
            onConfirm={() => onDelete(entry.knowledge_id)}
          >
            <Button
              size="small"
              type="text"
              danger
              icon={<DeleteOutlined />}
              onClick={(e) => e.stopPropagation()}
            />
          </Popconfirm>
        </Space>
      </div>
      <Paragraph
        type="secondary"
        ellipsis={{ rows: 2 }}
        className="text-sm mb-3"
      >
        {entry.description ?? "无描述"}
      </Paragraph>
      <div className="flex items-center justify-between">
        <Space size={4}>
          {entry.category && (
            <Tag color={CATEGORY_COLOR_MAP[entry.category] || "default"} className="text-xs">
              {entry.category}
            </Tag>
          )}
          {entry.defect_type && (
            <Tag className="text-xs">{entry.defect_type}</Tag>
          )}
        </Space>
        <Text type="secondary" className="text-xs">
          {entry.created_at ? dayjs(entry.created_at).format("MM-DD HH:mm") : ""}
        </Text>
      </div>
    </Card>
  );
}
