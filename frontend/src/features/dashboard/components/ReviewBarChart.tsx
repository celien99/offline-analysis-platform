import { Card } from "antd";
import Plot from "react-plotly.js";
import type { ClusterVizData } from "../../../types";
import { STATUS_COLORS } from "../../../lib/constants";

interface Props {
  summary: ClusterVizData["summary"];
}

export default function ReviewBarChart({ summary }: Props) {
  const barData: Plotly.Data[] = [
    {
      x: ["Real Defect", "False Alarm", "Pending Review"],
      y: [summary.real_defect, summary.false_alarm, summary.pending_review],
      type: "bar",
      marker: {
        color: [STATUS_COLORS.real_defect, STATUS_COLORS.false_alarm, STATUS_COLORS.pending_review],
      },
      text: [String(summary.real_defect), String(summary.false_alarm), String(summary.pending_review)],
      textposition: "auto",
    },
  ];

  return (
    <Card title="Review Status Distribution">
      <Plot
        data={barData}
        layout={{
          autosize: true,
          height: 450,
          margin: { l: 40, r: 20, t: 10, b: 40 },
          yaxis: { title: { text: "Count" }, dtick: 1 },
          showlegend: false,
        }}
        config={{ responsive: true, displayModeBar: false }}
        className="w-full"
        useResizeHandler
      />
    </Card>
  );
}
