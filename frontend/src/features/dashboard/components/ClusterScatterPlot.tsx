import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Card, Empty, Button } from "antd";
import Plot from "react-plotly.js";
import type { ScatterPoint } from "../../../types";
import { STATUS_COLORS } from "../../../lib/constants";

interface Props {
  points: ScatterPoint[];
}

export default function ClusterScatterPlot({ points }: Props) {
  const navigate = useNavigate();

  const handleClick = useCallback(
    (event: Plotly.PlotMouseEvent) => {
      const clusterId = (event.points[0] as { customdata?: string })?.customdata;
      if (!clusterId) return;
      navigate(`/clusters?cluster_id=${clusterId}`);
    },
    [navigate],
  );

  if (points.length === 0) {
    return (
      <Card title="聚类分布 (UMAP 投影)">
        <div className="flex flex-col items-center justify-center text-gray-400 py-12 h-[450px]">
          <Empty description="暂无聚类数据" />
          <Button type="primary" className="mt-3" onClick={() => navigate("/training")}>
            运行聚类任务
          </Button>
        </div>
      </Card>
    );
  }

  const statusGroups = new Map<string, ScatterPoint[]>();
  points.forEach((p) => {
    const key = p.review_status;
    if (!statusGroups.has(key)) statusGroups.set(key, []);
    statusGroups.get(key)!.push(p);
  });

  const plotData: Plotly.Data[] = [];
  for (const [status, group] of statusGroups) {
    plotData.push({
      x: group.map((p) => p.x),
      y: group.map((p) => p.y),
      type: "scatter",
      mode: "markers",
      name: status.replace(/_/g, " "),
      marker: {
        color: STATUS_COLORS[status] || "#8c8c8c",
        size: group.map((p) => Math.max(6, Math.min(30, Math.sqrt(p.sample_count) * 3))),
        line: { width: 0.5, color: "#fff" },
      },
      customdata: group.map((p) => p.cluster_id),
      text: group.map(
        (p) =>
          `<b>${p.name}</b><br>样本数: ${p.sample_count}<br>类型: ${p.possible_type}<br>缺陷: ${p.defect_type}<br><i>点击查看详情</i>`,
      ),
      hoverinfo: "text",
      hovertemplate: "%{text}<extra></extra>",
    } as Plotly.Data);
  }

  return (
    <Card title="聚类分布 (UMAP 投影)">
      <Plot
        data={plotData}
        layout={{
          autosize: true,
          height: 450,
          margin: { l: 40, r: 20, t: 10, b: 40 },
          xaxis: { title: { text: "UMAP-1" }, showgrid: true, zeroline: false },
          yaxis: { title: { text: "UMAP-2" }, showgrid: true, zeroline: false },
          legend: { x: 1, y: 1 },
          hovermode: "closest",
        }}
        config={{ responsive: true, displayModeBar: false }}
        className="w-full"
        useResizeHandler
        onClick={handleClick}
      />
    </Card>
  );
}
