import { Row, Col, Result, Button } from "antd";
import { useClusterVisualization } from "../../hooks/queries";
import SummaryStats from "./components/SummaryStats";
import ClusterScatterPlot from "./components/ClusterScatterPlot";
import ReviewBarChart from "./components/ReviewBarChart";
import { StatsSkeleton, TableSkeleton } from "../../components/ui/StateSkeleton";

export default function Dashboard() {
  const { data: vizData, isLoading, isError, refetch } = useClusterVisualization();

  if (isLoading) {
    return (
      <div>
        <StatsSkeleton />
        <Row gutter={[16, 16]} className="mt-6">
          <Col span={14}><TableSkeleton /></Col>
          <Col span={10}><TableSkeleton /></Col>
        </Row>
      </div>
    );
  }

  if (isError) {
    return (
      <Result
        status="error"
        title="加载数据面板失败"
        subTitle="无法加载可视化数据，请确认聚类任务已完成"
        extra={<Button onClick={() => refetch()}>重试</Button>}
      />
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
        <Col xs={24} lg={14}>
          <ClusterScatterPlot points={vizData?.scatter_data ?? []} />
        </Col>
        <Col xs={24} lg={10}>
          <ReviewBarChart summary={summary} />
        </Col>
      </Row>
    </div>
  );
}
