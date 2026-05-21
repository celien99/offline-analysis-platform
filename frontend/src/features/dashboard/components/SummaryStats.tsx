import { Card, Col, Row, Statistic } from "antd";
import {
  BugOutlined,
  ClusterOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from "@ant-design/icons";
import type { ClusterVizData } from "../../../types";

interface Props {
  summary: ClusterVizData["summary"];
}

export default function SummaryStats({ summary }: Props) {
  return (
    <Row gutter={[16, 16]}>
      <Col span={6}>
        <Card>
          <Statistic title="Total Anomalies" value={summary.total_samples} prefix={<BugOutlined />} />
        </Card>
      </Col>
      <Col span={6}>
        <Card>
          <Statistic title="Clusters" value={summary.total_clusters} prefix={<ClusterOutlined />} />
        </Card>
      </Col>
      <Col span={6}>
        <Card>
          <Statistic
            title="Real Defects"
            value={summary.real_defect}
            prefix={<CheckCircleOutlined />}
            valueStyle={{ color: "#ff4d4f" }}
          />
        </Card>
      </Col>
      <Col span={6}>
        <Card>
          <Statistic
            title="False Alarms"
            value={summary.false_alarm}
            prefix={<CloseCircleOutlined />}
            valueStyle={{ color: "#52c41a" }}
          />
        </Card>
      </Col>
    </Row>
  );
}
