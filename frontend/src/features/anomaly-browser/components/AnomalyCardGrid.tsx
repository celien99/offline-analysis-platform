import { Card, Tag, Progress, Typography, Empty } from "antd";
import { PhotoProvider, PhotoView } from "react-photo-view";
import "react-photo-view/dist/react-photo-view.css";
import type { AnomalyRecord } from "../../../types";
import { ANOMALY_STATUS_COLOR_MAP } from "../../../lib/constants";
import dayjs from "dayjs";

const { Text } = Typography;

interface Props {
  anomalies: AnomalyRecord[];
  onViewDetail: (id: string) => void;
}

export default function AnomalyCardGrid({ anomalies, onViewDetail }: Props) {
  if (anomalies.length === 0) {
    return <Empty description="暂无异常记录" />;
  }

  return (
    <PhotoProvider>
      <div
        className="grid gap-4"
        style={{ gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))" }}
      >
        {anomalies.map((a) => (
          <Card
            key={a.anomaly_id}
            hoverable
            className="industrial-card overflow-hidden"
            onClick={() => onViewDetail(a.anomaly_id)}
            classNames={{ body: "p-0" }}
          >
            <div className="h-48 bg-gray-100 overflow-hidden flex items-center justify-center">
              {(() => {
                const imgUrl = a.crop_url ?? a.original_url;
                return imgUrl ? (
                  <PhotoView src={imgUrl}>
                    <img
                      src={imgUrl}
                      alt={a.anomaly_id}
                      className="w-full h-full object-cover cursor-zoom-in"
                    />
                  </PhotoView>
                ) : (
                  <div className="text-gray-400 text-sm">无图像</div>
                );
              })()}
            </div>
            <div className="p-3">
              <div className="flex items-center justify-between mb-2">
                <Tag color="blue">{a.camera_id ?? "-"}</Tag>
                <Tag color={ANOMALY_STATUS_COLOR_MAP[a.status] || "default"}>
                  {a.status}
                </Tag>
              </div>
              {a.anomaly_score != null && (
                <div className="flex items-center gap-2 mb-1">
                  <Text type="secondary" className="text-xs">
                    异常分数
                  </Text>
                  <Progress
                    percent={Math.min(a.anomaly_score * 100, 100)}
                    showInfo={false}
                    size="small"
                    strokeColor={
                      a.anomaly_score > 0.5
                        ? "var(--color-defect)"
                        : "var(--color-false-alarm)"
                    }
                    className="flex-1"
                  />
                  <Text className="text-xs font-mono">
                    {a.anomaly_score.toFixed(3)}
                  </Text>
                </div>
              )}
              <Text type="secondary" className="text-xs">
                {a.created_at
                  ? dayjs(a.created_at).format("YYYY-MM-DD HH:mm")
                  : "-"}
              </Text>
            </div>
          </Card>
        ))}
      </div>
    </PhotoProvider>
  );
}
