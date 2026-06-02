import { Card } from "antd";

interface CameraNode {
  cameraId: string;
  patchcoreModel: string;
  filterModel?: string;
  normalizerModel?: string;
}

interface Props {
  seatModelId: string;
  yoloModel: string;
  projectorModel: string;
  whiteningModel: string;
  cameras: CameraNode[];
}

const MODEL_COLORS: Record<string, string> = {
  yolo: "#1677ff",
  patchcore: "#722ed1",
  filter: "#52c41a",
  normalizer: "#fa8c16",
  projector: "#eb2f96",
  whitening: "#13c2c2",
};

export default function CameraTopology({
  seatModelId, yoloModel, projectorModel, whiteningModel, cameras,
}: Props) {
  if (!seatModelId) {
    return (
      <Card title="配置拓扑" className="industrial-card mb-4">
        <div className="text-center text-gray-400 py-8">请先选择左侧座椅型号</div>
      </Card>
    );
  }

  if (cameras.length === 0) {
    return (
      <Card title="配置拓扑" className="industrial-card mb-4">
        <div className="text-center text-gray-400 py-8">该座椅型号下暂无相机配置</div>
      </Card>
    );
  }

  const NODE_W = 100;
  const NODE_H = 40;
  const ROW_H = 80;
  const svgHeight = Math.max(220, cameras.length * ROW_H + 100);

  return (
    <Card title="配置拓扑" className="industrial-card mb-4">
      <svg width="100%" viewBox={`0 0 ${800} ${svgHeight}`} className="max-w-[800px]">
        {/* Seat Model 节点 */}
        <rect x={20} y={svgHeight / 2 - 30} width={NODE_W} height={NODE_H * 1.5} rx={10}
          fill="#f0f5ff" stroke="#1677ff" strokeWidth={2} />
        <text x={20 + NODE_W / 2} y={svgHeight / 2} textAnchor="middle" fill="#1677ff" fontSize={13} fontWeight="bold">
          {seatModelId}
        </text>

        {/* 全局 YOLO 节点 */}
        <line x1={20 + NODE_W} y1={svgHeight / 2 - 20} x2={170} y2={svgHeight / 2 - 50}
          stroke={MODEL_COLORS.yolo} strokeWidth={1.5} />
        <rect x={170} y={svgHeight / 2 - 70} width={NODE_W} height={NODE_H} rx={6}
          fill="#fff" stroke={MODEL_COLORS.yolo} strokeWidth={1} />
        <text x={170 + NODE_W / 2} y={svgHeight / 2 - 58} textAnchor="middle" fill={MODEL_COLORS.yolo} fontSize={11} fontWeight="bold">
          YOLO
        </text>
        <text x={170 + NODE_W / 2} y={svgHeight / 2 - 40} textAnchor="middle" fill="#8c8c8c" fontSize={10}>
          {yoloModel && yoloModel !== "-" ? (yoloModel.length > 16 ? yoloModel.slice(0, 15) + "…" : yoloModel) : "未配置"}
        </text>

        {/* 全局 Calibration 节点 (Projector + Whitening) */}
        {[
          { label: "Projector", value: projectorModel, color: MODEL_COLORS.projector, yi: 0 },
          { label: "Whitening", value: whiteningModel, color: MODEL_COLORS.whitening, yi: 1 },
        ].map(({ label, value, color, yi }) => {
          const calX = 170;
          const calY = svgHeight / 2 + yi * 45;
          return (
            <g key={label}>
              <line x1={20 + NODE_W} y1={svgHeight / 2 + 15} x2={calX} y2={calY + NODE_H / 2}
                stroke={color} strokeWidth={1.5} strokeDasharray={value !== "-" ? "0" : "4"} />
              <rect x={calX} y={calY} width={NODE_W} height={NODE_H} rx={6} fill="#fff" stroke={color} strokeWidth={1}
                opacity={value !== "-" ? 1 : 0.5} />
              <text x={calX + NODE_W / 2} y={calY + 18} textAnchor="middle" fill={color} fontSize={11} fontWeight="bold">
                {label}
              </text>
              <text x={calX + NODE_W / 2} y={calY + 34} textAnchor="middle" fill="#8c8c8c" fontSize={10}>
                {value && value !== "-" ? (value.length > 14 ? value.slice(0, 13) + "…" : value) : "未配置"}
              </text>
            </g>
          );
        })}

        {cameras.map((cam, i) => {
          const y = 30 + i * ROW_H;
          const camX = 310;
          const modelStartX = 450;

          return (
            <g key={cam.cameraId}>
              {/* SeatModel → Camera 连线 */}
              <line x1={20 + NODE_W} y1={svgHeight / 2} x2={camX} y2={y + NODE_H / 2}
                stroke="#d9d9d9" strokeWidth={1.5} />

              {/* Camera 节点 */}
              <rect x={camX} y={y} width={NODE_W} height={NODE_H} rx={6} fill="#fff" stroke="#8c8c8c" strokeWidth={1} />
              <text x={camX + NODE_W / 2} y={y + 26} textAnchor="middle" fill="#333" fontSize={12} fontWeight="bold">
                {cam.cameraId}
              </text>

              {/* 每台相机的模型 */}
              {[
                { label: "PC", value: cam.patchcoreModel, color: MODEL_COLORS.patchcore },
                { label: "Norm", value: cam.normalizerModel, color: MODEL_COLORS.normalizer },
                cam.filterModel ? { label: "FC", value: cam.filterModel, color: MODEL_COLORS.filter } : null,
              ].filter(Boolean).map((m, mi) => {
                if (!m) return null;
                const mx = modelStartX + mi * 115;
                return (
                  <g key={m.label}>
                    <line x1={camX + NODE_W} y1={y + NODE_H / 2} x2={mx} y2={y + NODE_H / 2}
                      stroke={m.color} strokeWidth={1.5} />
                    <rect x={mx} y={y} width={90} height={NODE_H} rx={6} fill="#fff" stroke={m.color} strokeWidth={1} />
                    <text x={mx + 45} y={y + 18} textAnchor="middle" fill={m.color} fontSize={11} fontWeight="bold">
                      {m.label}
                    </text>
                    <text x={mx + 45} y={y + 34} textAnchor="middle" fill="#8c8c8c" fontSize={10}>
                      {m.value && m.value !== "-" ? (m.value.length > 12 ? m.value.slice(0, 11) + "…" : m.value) : "未配置"}
                    </text>
                  </g>
                );
              })}
            </g>
          );
        })}
      </svg>
      <div className="flex gap-4 mt-3 text-xs text-gray-400 flex-wrap">
        <span><span className="inline-block w-3 h-3 rounded mr-1" style={{ background: MODEL_COLORS.yolo }} />YOLO（全局）</span>
        <span><span className="inline-block w-3 h-3 rounded mr-1" style={{ background: MODEL_COLORS.patchcore }} />PatchCore</span>
        <span><span className="inline-block w-3 h-3 rounded mr-1" style={{ background: MODEL_COLORS.normalizer }} />Normalizer</span>
        <span><span className="inline-block w-3 h-3 rounded mr-1" style={{ background: MODEL_COLORS.filter }} />Filter</span>
        <span><span className="inline-block w-3 h-3 rounded mr-1" style={{ background: MODEL_COLORS.projector }} />Projector</span>
        <span><span className="inline-block w-3 h-3 rounded mr-1" style={{ background: MODEL_COLORS.whitening }} />Whitening</span>
      </div>
    </Card>
  );
}
