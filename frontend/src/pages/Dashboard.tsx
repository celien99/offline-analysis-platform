import { useEffect, useState } from "react";
import { Card, Col, Row, Statistic, Spin } from "antd";
import {
  BugOutlined,
  ClusterOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from "@ant-design/icons";
import Plot from "react-plotly.js";
import axios from "axios";

interface ScatterPoint {
  cluster_id: string;
  name: string;
  x: number;
  y: number;
  sample_count: number;
  possible_type: string;
  review_status: string;
  defect_type: string;
}

interface ClusterVizData {
  scatter_data: ScatterPoint[];
  summary: {
    total_clusters: number;
    total_samples: number;
    real_defect: number;
    false_alarm: number;
    pending_review: number;
  };
}

const STATUS_COLORS: Record<string, string> = {
  real_defect: "#ff4d4f",
  false_alarm: "#52c41a",
  pending_review: "#faad14",
};

export default function Dashboard() {
  const [vizData, setVizData] = useState<ClusterVizData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios
      .get("/api/cluster/visualization")
      .then((res) => setVizData(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div style={{ textAlign: "center", padding: 80 }}>
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

  const scatterData = vizData?.scatter_data ?? [];

  const plotData: Plotly.Data[] = [];
  const statusGroups = new Map<string, ScatterPoint[]>();
  scatterData.forEach((p) => {
    const key = p.review_status;
    if (!statusGroups.has(key)) statusGroups.set(key, []);
    statusGroups.get(key)!.push(p);
  });

  for (const [status, points] of statusGroups) {
    plotData.push({
      x: points.map((p) => p.x),
      y: points.map((p) => p.y),
      type: "scatter",
      mode: "markers",
      name: status.replace(/_/g, " "),
      marker: {
        color: STATUS_COLORS[status] || "#8c8c8c",
        size: points.map((p) => Math.max(6, Math.min(30, Math.sqrt(p.sample_count) * 3))),
        line: { width: 0.5, color: "#fff" },
      },
      text: points.map(
        (p) =>
          `<b>${p.name}</b><br>` +
          `Samples: ${p.sample_count}<br>` +
          `Type: ${p.possible_type}<br>` +
          `Defect: ${p.defect_type}`
      ),
      hoverinfo: "text",
      hovertemplate: "%{text}<extra></extra>",
    } as Plotly.Data);
  }

  const barData: Plotly.Data[] = [
    {
      x: ["Real Defect", "False Alarm", "Pending Review"],
      y: [summary.real_defect, summary.false_alarm, summary.pending_review],
      type: "bar",
      marker: {
        color: [STATUS_COLORS.real_defect, STATUS_COLORS.false_alarm, STATUS_COLORS.pending_review],
      },
      text: [summary.real_defect, summary.false_alarm, summary.pending_review],
      textposition: "auto",
    },
  ];

  return (
    <div>
      <Row gutter={[16, 16]}>
        <Col span={6}>
          <Card>
            <Statistic
              title="Total Anomalies"
              value={summary.total_samples}
              prefix={<BugOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="Clusters"
              value={summary.total_clusters}
              prefix={<ClusterOutlined />}
            />
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

      <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
        <Col span={14}>
          <Card title="Cluster Distribution (UMAP 2D Projection)">
            {scatterData.length > 0 ? (
              <Plot
                data={plotData}
                layout={{
                  autosize: true,
                  height: 450,
                  margin: { l: 40, r: 20, t: 10, b: 40 },
                  xaxis: { title: "UMAP-1", showgrid: true, zeroline: false },
                  yaxis: { title: "UMAP-2", showgrid: true, zeroline: false },
                  legend: { x: 1, y: 1 },
                  hovermode: "closest",
                }}
                config={{ responsive: true, displayModeBar: false }}
                style={{ width: "100%" }}
                useResizeHandler
              />
            ) : (
              <div
                style={{
                  height: 450,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#8c8c8c",
                }}
              >
                No cluster data yet. Run clustering to see visualization.
              </div>
            )}
          </Card>
        </Col>
        <Col span={10}>
          <Card title="Review Status Distribution">
            <Plot
              data={barData}
              layout={{
                autosize: true,
                height: 450,
                margin: { l: 40, r: 20, t: 10, b: 40 },
                yaxis: { title: "Count", dtick: 1 },
                showlegend: false,
              }}
              config={{ responsive: true, displayModeBar: false }}
              style={{ width: "100%" }}
              useResizeHandler
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
}
