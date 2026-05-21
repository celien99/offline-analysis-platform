import { Row, Col } from "antd";
import { useApi } from "../../hooks/useApi";
import { clusterApi } from "../../api";
import type { ClusterVizData } from "../../types";
import SummaryStats from "./components/SummaryStats";
import ClusterScatterPlot from "./components/ClusterScatterPlot";
import ReviewBarChart from "./components/ReviewBarChart";
import { Spin } from "antd";

export default function Dashboard() {
  const { data: vizData, loading } = useApi<ClusterVizData>(
    () => clusterApi.visualization() as Promise<ClusterVizData>,
    [],
    { silent: true },
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spin size="large" />
      </div>
    );
  }

  const summary = vizData?.summary ?? {
    total_clusters: 0,
    total_samples: 0,
    real_defect: 0,
    false_alarm: 0,
    pending_review: 0,
  };

  return (
    <div>
      <SummaryStats summary={summary} />
      <Row gutter={[16, 16]} className="mt-6">
        <Col span={14}>
          <ClusterScatterPlot points={vizData?.scatter_data ?? []} />
        </Col>
        <Col span={10}>
          <ReviewBarChart summary={summary} />
        </Col>
      </Row>
    </div>
  );
}
