import { Card, Descriptions, Tag, Table, Typography } from "antd";
import type { EvalResult } from "../../../types";
import { RULE_TYPE_COLOR_MAP } from "../../../lib/constants";

const { Text } = Typography;

interface Props {
  result: EvalResult;
}

export default function EvalResultDisplay({ result }: Props) {
  return (
    <Card title="Evaluation Result" size="small" className="mt-4">
      <Descriptions column={2} size="small">
        <Descriptions.Item label="Final Action">
          <Tag
            color={result.action === "ignore" ? "green" : result.action === "escalate" ? "red" : "orange"}
            className="text-sm px-2 py-1"
          >
            {result.action.toUpperCase()}
          </Tag>
        </Descriptions.Item>
        <Descriptions.Item label="Rules Matched">
          <Text strong>{result.rule_count}</Text>
        </Descriptions.Item>
      </Descriptions>
      {result.matched_rules.length > 0 && (
        <Table
          className="mt-3"
          dataSource={result.matched_rules}
          rowKey="rule_id"
          size="small"
          pagination={false}
          columns={[
            { title: "Name", dataIndex: "name", key: "name" },
            {
              title: "Type",
              dataIndex: "type",
              key: "type",
              render: (t: string) => <Tag color={RULE_TYPE_COLOR_MAP[t] || "default"}>{t}</Tag>,
            },
            { title: "Priority", dataIndex: "priority", key: "priority" },
          ]}
        />
      )}
    </Card>
  );
}
