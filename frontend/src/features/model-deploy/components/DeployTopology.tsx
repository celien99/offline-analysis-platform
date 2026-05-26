import { Card } from "antd";

interface Props {
  targets?: { target: string; activeModel: string; activeVersion: string; hasShadow: boolean }[];
}

export default function DeployTopology({ targets }: Props) {
  const data = targets ?? [];

  if (data.length === 0) {
    return (
      <Card title="部署拓扑" className="industrial-card mb-4">
        <div className="text-center text-gray-400 py-8">暂无部署数据</div>
      </Card>
    );
  }

  const NODE_W = 140;
  const NODE_H = 52;
  const GAP_X = 180;
  const GAP_Y = 80;
  const SVG_W = 600;
  const SVG_H = Math.max(200, data.length * GAP_Y + 40);

  return (
    <Card title="部署拓扑" className="industrial-card mb-4">
      <svg width="100%" viewBox={`0 0 ${SVG_W} ${SVG_H}`} style={{ maxWidth: SVG_W }}>
        {data.map((item, i) => {
          const y = 30 + i * GAP_Y;
          const x1 = 30;
          const x2 = x1 + GAP_X;
          const x3 = x2 + GAP_X;

          return (
            <g key={item.target}>
              <line x1={x1 + NODE_W} y1={y + NODE_H / 2} x2={x2} y2={y + NODE_H / 2}
                stroke="#d9d9d9" strokeWidth={2} />
              <rect x={x1} y={y} width={NODE_W} height={NODE_H} rx={8} fill="#f0f5ff" stroke="#1677ff" strokeWidth={1.5} />
              <text x={x1 + NODE_W / 2} y={y + 20} textAnchor="middle" fill="#1677ff" fontSize={12} fontWeight="bold">
                {item.target}
              </text>
              <text x={x1 + NODE_W / 2} y={y + 38} textAnchor="middle" fill="#8c8c8c" fontSize={11}>
                目标
              </text>

              <rect x={x2} y={y} width={NODE_W} height={NODE_H} rx={8} fill="#f6ffed" stroke="#52c41a" strokeWidth={1.5} />
              <text x={x2 + NODE_W / 2} y={y + 18} textAnchor="middle" fill="#52c41a" fontSize={12} fontWeight="bold">
                {item.activeModel}
              </text>
              <text x={x2 + NODE_W / 2} y={y + 36} textAnchor="middle" fill="#8c8c8c" fontSize={11}>
                {item.activeVersion}
              </text>

              {item.hasShadow && (
                <>
                  <line x1={x2 + NODE_W} y1={y + NODE_H / 2} x2={x3} y2={y + NODE_H / 2}
                    stroke="#faad14" strokeWidth={1.5} strokeDasharray="5,3" />
                  <rect x={x3} y={y} width={NODE_W} height={NODE_H} rx={8} fill="#fffbe6" stroke="#faad14" strokeWidth={1.5} />
                  <text x={x3 + NODE_W / 2} y={y + 20} textAnchor="middle" fill="#faad14" fontSize={12} fontWeight="bold">
                    影子模型
                  </text>
                  <text x={x3 + NODE_W / 2} y={y + 38} textAnchor="middle" fill="#8c8c8c" fontSize={11}>
                    待重载
                  </text>
                </>
              )}
            </g>
          );
        })}
      </svg>
      <div className="flex gap-4 mt-3 text-xs text-gray-400">
        <span><span className="inline-block w-3 h-3 rounded bg-blue-500 mr-1" /> 目标</span>
        <span><span className="inline-block w-3 h-3 rounded bg-green-500 mr-1" /> 活跃模型</span>
        <span><span className="inline-block w-3 h-3 rounded bg-yellow-500 mr-1" /> 影子模型</span>
      </div>
    </Card>
  );
}
