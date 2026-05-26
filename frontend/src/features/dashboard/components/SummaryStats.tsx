import { useEffect, useState } from "react";
import { Card, Col, Row } from "antd";
import {
  BugOutlined,
  ClusterOutlined,
  CheckCircleOutlined,
  QuestionCircleOutlined,
} from "@ant-design/icons";
import type { ClusterVizData } from "../../../types";

interface Props {
  summary: ClusterVizData["summary"];
}

function useCountUp(target: number, duration = 600) {
  const [value, setValue] = useState(0);
  useEffect(() => {
    let start = 0;
    const step = Math.ceil(target / (duration / 16));
    const timer = setInterval(() => {
      start += step;
      if (start >= target) {
        setValue(target);
        clearInterval(timer);
      } else {
        setValue(start);
      }
    }, 16);
    return () => clearInterval(timer);
  }, [target, duration]);
  return value;
}

function AnimatedStatistic({
  title,
  value,
  icon,
  color,
}: {
  title: string;
  value: number;
  icon: React.ReactNode;
  color?: string;
}) {
  const animated = useCountUp(value);
  return (
    <Card classNames={{ body: "py-4 px-5" }}>
      <div className="flex items-center gap-3">
        <div className="text-2xl" style={{ color: color ?? "var(--color-primary)" }}>
          {icon}
        </div>
        <div>
          <div className="text-xs text-gray-400">{title}</div>
          <div className="text-2xl font-bold" style={{ color: color ?? "inherit" }}>
            {animated}
          </div>
        </div>
      </div>
    </Card>
  );
}

export default function SummaryStats({ summary }: Props) {
  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} sm={12} md={6}>
        <AnimatedStatistic
          title="异常总数"
          value={summary.total_samples}
          icon={<BugOutlined />}
          color="var(--color-primary)"
        />
      </Col>
      <Col xs={24} sm={12} md={6}>
        <AnimatedStatistic
          title="聚类数"
          value={summary.total_clusters}
          icon={<ClusterOutlined />}
          color="var(--color-primary)"
        />
      </Col>
      <Col xs={24} sm={12} md={6}>
        <AnimatedStatistic
          title="真实缺陷"
          value={summary.real_defect}
          icon={<CheckCircleOutlined />}
          color="var(--color-defect)"
        />
      </Col>
      <Col xs={24} sm={12} md={6}>
        <AnimatedStatistic
          title="待审核"
          value={summary.pending_review}
          icon={<QuestionCircleOutlined />}
          color="var(--color-pending)"
        />
      </Col>
    </Row>
  );
}
