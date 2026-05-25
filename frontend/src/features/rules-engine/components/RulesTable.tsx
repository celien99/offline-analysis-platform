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
      title: "名称",
      dataIndex: "name",
      key: "name",
      render: (n: string) => <Text strong>{n}</Text>,
    },
    {
      title: "类型",
      dataIndex: "rule_type",
      key: "rule_type",
      width: 90,
      render: (t: string) => (
        <Tag color={RULE_TYPE_COLOR_MAP[t] || "default"}>{t.toUpperCase()}</Tag>
      ),
    },
    {
      title: "优先级",
      dataIndex: "priority",
      key: "priority",
      width: 70,
      sorter: (a, b) => a.priority - b.priority,
    },
    {
      title: "启用",
      dataIndex: "enabled",
      key: "enabled",
      width: 80,
      render: (enabled: boolean, record: Rule) => (
        <Switch checked={enabled} size="small" onChange={(checked) => onToggle(record.rule_id, checked)} />
      ),
    },
    {
      title: "描述",
      dataIndex: "description",
      key: "description",
      ellipsis: true,
      render: (d: string | null) => <Text type="secondary">{d || "-"}</Text>,
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      key: "created_at",
      width: 170,
      render: (d: string) => new Date(d).toLocaleString(),
    },
    {
      title: "操作",
      key: "actions",
      width: 100,
      render: (_: unknown, record: Rule) => (
        <Popconfirm title="确定要删除此规则吗？" onConfirm={() => onDelete(record.rule_id)}>
          <Button type="link" size="small" danger icon={<DeleteOutlined />}>
            删除
          </Button>
        </Popconfirm>
      ),
    },
  ];
}
