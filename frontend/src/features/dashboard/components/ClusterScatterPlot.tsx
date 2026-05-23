import { useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Card } from "antd";
import Plot from "react-plotly.js";
import type { ScatterPoint } from "../../../types";
import { STATUS_COLORS } from "../../../lib/constants";

interface Props {
  points: ScatterPoint[];
}

export default function ClusterScatterPlot({ points }: Props) {
  const navigate = useNavigate();

  // 按照绘图顺序构建 cluster_id 扁平数组，供点击事件反查
  const clusterIdOrder = useMemo(() => {
    const groups = new Map<string, ScatterPoint[]>();
    points.forEach((p) => {
      const key = p.review_status;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(p);
    });
    const order: string[] = [];
    for (const group of groups.values()) {
      for (const p of group) {
        order.push(p.cluster_id);
      }
    }
    return order;
  }, [points]);

  const handleClick = useCallback(
    (event: Plotly.PlotMouseEvent) => {
      const idx = event.points[0]?.pointIndex;
      if (idx == null || idx >= clusterIdOrder.length) return;
      navigate(`/clusters?cluster_id=${clusterIdOrder[idx]}`);
    },
    [navigate, clusterIdOrder],
  );

  if (points.length === 0) {
    return (
      <Card title="Cluster Distribution (UMAP 2D Projection)">
        <div className="flex items-center justify-center text-gray-400" style={{ height: 450 }}>
          No cluster data yet. Run clustering to see visualization.
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
      text: group.map(
        (p) =>
          `<b>${p.name}</b><br>Samples: ${p.sample_count}<br>Type: ${p.possible_type}<br>Defect: ${p.defect_type}<br><i>Click to view detail</i>`,
      ),
      hoverinfo: "text",
      hovertemplate: "%{text}<extra></extra>",
    } as Plotly.Data);
  }

  return (
    <Card title="Cluster Distribution (UMAP 2D Projection)">
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
