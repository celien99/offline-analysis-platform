import { useState } from "react";
import { Modal, Descriptions, Tag, Row, Col, Button, Table, Typography } from "antd";
import { SearchOutlined } from "@ant-design/icons";
import { PhotoProvider, PhotoView } from "react-photo-view";
import type { AnomalyRecord } from "../../../types";
import { anomalyApi } from "../../../api";
import { ANOMALY_STATUS_COLOR_MAP } from "../../../lib/constants";

const { Text } = Typography;

interface Props {
  anomaly: AnomalyRecord | null;
  open: boolean;
  onClose: () => void;
}

export default function AnomalyDetailModal({ anomaly, open, onClose }: Props) {
  const [similarResults, setSimilarResults] = useState<unknown[]>([]);
  const [searchingSimilar, setSearchingSimilar] = useState(false);

  if (!anomaly) return null;

  const handleSearchSimilar = async () => {
    setSearchingSimilar(true);
    try {
      const results = await anomalyApi.searchSimilar(anomaly.anomaly_id);
      setSimilarResults(Array.isArray(results) ? results : []);
    } catch {
      /* handled by interceptor */
    } finally {
      setSearchingSimilar(false);
    }
  };

  return (
    <Modal title="Anomaly Detail" open={open} onCancel={onClose} footer={null} width={900}>
      <Descriptions column={2} bordered size="small" className="mb-4">
        <Descriptions.Item label="ID">{anomaly.anomaly_id}</Descriptions.Item>
        <Descriptions.Item label="Camera">{anomaly.camera_id}</Descriptions.Item>
        <Descriptions.Item label="Source">{anomaly.source}</Descriptions.Item>
        <Descriptions.Item label="Score">{anomaly.anomaly_score?.toFixed(3) ?? "-"}</Descriptions.Item>
        <Descriptions.Item label="Status">
          <Tag color={ANOMALY_STATUS_COLOR_MAP[anomaly.status]}>{anomaly.status}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="Date">{anomaly.date_folder}</Descriptions.Item>
      </Descriptions>

      <Row gutter={8} className="mb-4">
        <PhotoProvider>
          {anomaly.crop_url && (
            <Col span={6}>
              <Text strong>Crop</Text>
              <PhotoView src={anomaly.crop_url}>
                <img src={anomaly.crop_url} alt="crop" className="w-full cursor-zoom-in rounded object-cover" />
              </PhotoView>
            </Col>
          )}
          {anomaly.roi_url && (
            <Col span={6}>
              <Text strong>ROI</Text>
              <PhotoView src={anomaly.roi_url}>
                <img src={anomaly.roi_url} alt="roi" className="w-full cursor-zoom-in rounded object-cover" />
              </PhotoView>
            </Col>
          )}
          {anomaly.heatmap_url && (
            <Col span={6}>
              <Text strong>Heatmap</Text>
              <PhotoView src={anomaly.heatmap_url}>
                <img src={anomaly.heatmap_url} alt="heatmap" className="w-full cursor-zoom-in rounded object-cover" />
              </PhotoView>
            </Col>
          )}
          {anomaly.original_url && (
            <Col span={6}>
              <Text strong>Original</Text>
              <PhotoView src={anomaly.original_url}>
                <img src={anomaly.original_url} alt="original" className="w-full cursor-zoom-in rounded object-cover" />
              </PhotoView>
            </Col>
          )}
        </PhotoProvider>
      </Row>

      <Button icon={<SearchOutlined />} onClick={handleSearchSimilar} loading={searchingSimilar}>
        Find Similar
      </Button>

      {similarResults.length > 0 && (
        <div className="mt-4">
          <Text strong>Similar Anomalies ({similarResults.length})</Text>
          <Table
            className="mt-2"
            dataSource={similarResults}
            columns={[
              {
                title: "Anomaly ID",
                dataIndex: "anomaly_id",
                key: "id",
                render: (id: string) => <Text code>{String(id).slice(0, 12)}...</Text>,
              },
              {
                title: "Similarity",
                dataIndex: "similarity",
                key: "sim",
                render: (s: number) => (
                  <Tag color={s > 0.9 ? "green" : "orange"}>{(s * 100).toFixed(1)}%</Tag>
                ),
              },
            ]}
            pagination={false}
            size="small"
            rowKey="anomaly_id"
          />
        </div>
      )}
    </Modal>
  );
}
