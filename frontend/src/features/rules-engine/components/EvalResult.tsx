import { Card, Statistic, Tag, Typography, Row, Col, Empty } from "antd";
import { CheckCircleOutlined, CloseCircleOutlined } from "@ant-design/icons";
import type { EvalResult } from "../../../types";

const { Text } = Typography;

interface Props {
  result: EvalResult;
}

export default function EvalResultDisplay({ result }: Props) {
  const isIgnore = result.action === "ignore";
  const isEscalate = result.action === "escalate";

  return (
    <Card title="评估结果" className="mt-4 industrial-card">
      <Row gutter={[24, 16]}>
        <Col span={8}>
          <Statistic
            title="最终动作"
            value={result.action.toUpperCase()}
            valueStyle={{ color: isEscalate ? "var(--color-defect)" : isIgnore ? "var(--color-false-alarm)" : "var(--color-pending)" }}
            prefix={isIgnore ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
          />
        </Col>
        <Col span={8}>
          <Statistic title="匹配规则数" value={result.rule_count} />
        </Col>
        <Col span={8}>
          <Statistic title="匹配样本数" value={result.matched_rules?.length ?? 0} />
        </Col>
      </Row>

      {result.matched_rules && result.matched_rules.length > 0 ? (
        <div className="mt-4">
          <Text strong className="block mb-2">命中规则</Text>
          {result.matched_rules.map((rule) => (
            <Tag key={rule.rule_id} color="green" className="mb-1">
              {rule.name} (优先级: {rule.priority})
            </Tag>
          ))}
        </div>
      ) : (
        <Empty description="无匹配规则" className="mt-4" />
      )}
    </Card>
  );
}
