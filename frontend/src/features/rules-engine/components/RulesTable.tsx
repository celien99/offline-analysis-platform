import { Switch, Tag, Button, Popconfirm, Typography } from "antd";
import { DeleteOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import type { Rule } from "../../../types";
import { RULE_TYPE_COLOR_MAP } from "../../../lib/constants";

const { Text } = Typography;

interface Props {
  onToggle: (ruleId: string, enabled: boolean) => void;
  onDelete: (ruleId: string) => void;
}

export function useRulesColumns({ onToggle, onDelete }: Props): ColumnsType<Rule> {
  return [
    {
      title: "Name",
      dataIndex: "name",
      key: "name",
      render: (n: string) => <Text strong>{n}</Text>,
    },
    {
      title: "Type",
      dataIndex: "rule_type",
      key: "rule_type",
      width: 90,
      render: (t: string) => (
        <Tag color={RULE_TYPE_COLOR_MAP[t] || "default"}>{t.toUpperCase()}</Tag>
      ),
    },
    {
      title: "Priority",
      dataIndex: "priority",
      key: "priority",
      width: 70,
      sorter: (a, b) => a.priority - b.priority,
    },
    {
      title: "Enabled",
      dataIndex: "enabled",
      key: "enabled",
      width: 80,
      render: (enabled: boolean, record: Rule) => (
        <Switch checked={enabled} size="small" onChange={(checked) => onToggle(record.rule_id, checked)} />
      ),
    },
    {
      title: "Description",
      dataIndex: "description",
      key: "description",
      ellipsis: true,
      render: (d: string | null) => <Text type="secondary">{d || "-"}</Text>,
    },
    {
      title: "Created",
      dataIndex: "created_at",
      key: "created_at",
      width: 170,
      render: (d: string) => new Date(d).toLocaleString(),
    },
    {
      title: "Actions",
      key: "actions",
      width: 100,
      render: (_: unknown, record: Rule) => (
        <Popconfirm title="Delete this rule?" onConfirm={() => onDelete(record.rule_id)}>
          <Button type="link" size="small" danger icon={<DeleteOutlined />}>
            Delete
          </Button>
        </Popconfirm>
      ),
    },
  ];
}
