import { Card } from "antd";
import Plot from "react-plotly.js";
import type { ScatterPoint } from "../../../types";
import { STATUS_COLORS } from "../../../lib/constants";

interface Props {
  points: ScatterPoint[];
}

export default function ClusterScatterPlot({ points }: Props) {
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
          `<b>${p.name}</b><br>Samples: ${p.sample_count}<br>Type: ${p.possible_type}<br>Defect: ${p.defect_type}`,
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
      />
    </Card>
  );
}
