import { useState } from "react";
import { Modal, Descriptions, Tag, Row, Col, Button, Table, Typography } from "antd";
import { SearchOutlined, ClusterOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
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
  const navigate = useNavigate();
  const [similarResults, setSimilarResults] = useState<unknown[]>([]);
  const [searchingSimilar, setSearchingSimilar] = useState(false);

  if (!anomaly) return null;

  const allCropUrls = [anomaly.crop_url, ...(anomaly.crop_urls ?? [])].filter(Boolean) as string[];
  const cropItems = allCropUrls.map((url, i) => ({
    label: allCropUrls.length > 1 ? `Crop ${i + 1}` : "Crop",
    url,
    alt: `crop-${i}`,
  }));

  const imageItems = [
    { label: "Original", url: anomaly.original_url, alt: "original" },
    { label: "Heatmap", url: anomaly.heatmap_url, alt: "heatmap" },
    ...cropItems,
  ].filter((item): item is { label: string; url: string; alt: string } => Boolean(item.url));

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
        <Descriptions.Item label="Cluster" span={2}>
          {anomaly.cluster_id ? (
            <Button
              type="link"
              icon={<ClusterOutlined />}
              onClick={() => { navigate(`/clusters?cluster_id=${anomaly.cluster_id}`); onClose(); }}
            >
              {anomaly.cluster_id}
            </Button>
          ) : (
            <Text type="secondary">未分配</Text>
          )}
        </Descriptions.Item>
      </Descriptions>

      <Row gutter={[8, 12]} className="mb-4">
        <PhotoProvider>
          {imageItems.map((item) => (
            <Col span={Math.min(8, Math.floor(24 / Math.max(1, imageItems.length)))} key={item.alt}>
              <Text strong>{item.label}</Text>
              <PhotoView src={item.url}>
                <img src={item.url} alt={item.alt} className="w-full cursor-zoom-in rounded object-cover" />
              </PhotoView>
            </Col>
          ))}
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
