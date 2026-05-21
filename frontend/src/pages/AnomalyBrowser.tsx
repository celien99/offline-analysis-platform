import { useEffect, useState } from "react";
import {
  Card,
  Table,
  Tag,
  Button,
  Space,
  Row,
  Col,
  Input,
  Select,
  Modal,
  Descriptions,
  message,
  Typography,
} from "antd";
import { ReloadOutlined, SearchOutlined, RetweetOutlined } from "@ant-design/icons";
import { PhotoProvider, PhotoView } from "react-photo-view";
import "react-photo-view/dist/react-photo-view.css";
import type { AnomalyRecord } from "../types";
import { fetchAnomalies, fetchAnomalyDetail, searchSimilar, reprocessAnomaly } from "../api/client";

const { Text } = Typography;

export default function AnomalyBrowser() {
  const [anomalies, setAnomalies] = useState<AnomalyRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [cameraFilter, setCameraFilter] = useState<string | undefined>();
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [selectedAnomaly, setSelectedAnomaly] = useState<AnomalyRecord | null>(null);
  const [detailVisible, setDetailVisible] = useState(false);
  const [similarResults, setSimilarResults] = useState<unknown[]>([]);
  const [searchingSimilar, setSearchingSimilar] = useState(false);

  const loadAnomalies = async (p = page) => {
    setLoading(true);
    try {
      const data = await fetchAnomalies({
        page: p,
        page_size: 20,
        camera_id: cameraFilter,
        status: statusFilter,
      });
      setAnomalies(data);
    } catch {
      message.error("Failed to load anomalies");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAnomalies();
  }, [page, cameraFilter, statusFilter]);

  const handleViewDetail = async (anomalyId: string) => {
    try {
      const detail = await fetchAnomalyDetail(anomalyId);
      setSelectedAnomaly(detail);
      setDetailVisible(true);
      setSimilarResults([]);
    } catch {
      message.error("Failed to load anomaly detail");
    }
  };

  const handleSearchSimilar = async (anomalyId: string) => {
    setSearchingSimilar(true);
    try {
      const results = await searchSimilar(anomalyId);
      setSimilarResults(Array.isArray(results) ? results : []);
    } catch {
      message.error("Similarity search failed");
    } finally {
      setSearchingSimilar(false);
    }
  };

  const handleReprocess = async (anomalyId: string) => {
    try {
      await reprocessAnomaly(anomalyId);
      message.success("Anomaly queued for reprocessing");
      loadAnomalies();
    } catch {
      message.error("Reprocess failed");
    }
  };

  const statusColorMap: Record<string, string> = {
    pending: "orange",
    embedded: "blue",
    clustered: "cyan",
    reviewed: "green",
  };

  const columns = [
    {
      title: "ID",
      dataIndex: "anomaly_id",
      key: "anomaly_id",
      render: (id: string) => (
        <Text code>{id.slice(0, 12)}...</Text>
      ),
    },
    {
      title: "Camera",
      dataIndex: "camera_id",
      key: "camera_id",
    },
    {
      title: "Source",
      dataIndex: "source",
      key: "source",
      render: (s: string) => <Tag>{s}</Tag>,
    },
    {
      title: "Score",
      dataIndex: "anomaly_score",
      key: "anomaly_score",
      render: (s: number | null) =>
        s !== null ? s.toFixed(3) : "-",
    },
    {
      title: "Date",
      dataIndex: "date_folder",
      key: "date_folder",
    },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      render: (s: string) => (
        <Tag color={statusColorMap[s] || "default"}>{s}</Tag>
      ),
    },
    {
      title: "Actions",
      key: "actions",
      render: (_: unknown, record: AnomalyRecord) => (
        <Space>
          <Button
            type="link"
            size="small"
            onClick={() => handleViewDetail(record.anomaly_id)}
          >
            Detail
          </Button>
          <Button
            type="link"
            size="small"
            icon={<RetweetOutlined />}
            onClick={() => handleReprocess(record.anomaly_id)}
          >
            Reprocess
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <h2>Anomaly Browser</h2>
        </Col>
        <Col>
          <Space>
            <Input
              placeholder="Camera ID"
              allowClear
              style={{ width: 150 }}
              value={cameraFilter}
              onChange={(e) => setCameraFilter(e.target.value || undefined)}
            />
            <Select
              placeholder="Status"
              allowClear
              style={{ width: 130 }}
              value={statusFilter}
              onChange={setStatusFilter}
              options={[
                { value: "pending", label: "Pending" },
                { value: "embedded", label: "Embedded" },
                { value: "clustered", label: "Clustered" },
                { value: "reviewed", label: "Reviewed" },
              ]}
            />
            <Button icon={<ReloadOutlined />} onClick={() => loadAnomalies()}>
              Refresh
            </Button>
          </Space>
        </Col>
      </Row>

      <Card>
        <Table
          columns={columns}
          dataSource={anomalies}
          rowKey="anomaly_id"
          loading={loading}
          pagination={{
            current: page,
            pageSize: 20,
            onChange: setPage,
          }}
        />
      </Card>

      <Modal
        title="Anomaly Detail"
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={null}
        width={900}
      >
        {selectedAnomaly && (
          <div>
            <Descriptions column={2} bordered size="small" style={{ marginBottom: 16 }}>
              <Descriptions.Item label="ID">{selectedAnomaly.anomaly_id}</Descriptions.Item>
              <Descriptions.Item label="Camera">{selectedAnomaly.camera_id}</Descriptions.Item>
              <Descriptions.Item label="Source">{selectedAnomaly.source}</Descriptions.Item>
              <Descriptions.Item label="Score">
                {selectedAnomaly.anomaly_score?.toFixed(3) ?? "-"}
              </Descriptions.Item>
              <Descriptions.Item label="Status">
                <Tag color={statusColorMap[selectedAnomaly.status]}>
                  {selectedAnomaly.status}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Date">{selectedAnomaly.date_folder}</Descriptions.Item>
            </Descriptions>

            <Row gutter={8} style={{ marginBottom: 16 }}>
              <PhotoProvider>
                {selectedAnomaly.crop_url && (
                  <Col span={6}>
                    <Text strong>Crop</Text>
                    <PhotoView src={selectedAnomaly.crop_url}>
                      <img
                        src={selectedAnomaly.crop_url}
                        alt="crop"
                        style={{ width: "100%", cursor: "zoom-in", borderRadius: 6, objectFit: "cover" }}
                      />
                    </PhotoView>
                  </Col>
                )}
                {selectedAnomaly.roi_url && (
                  <Col span={6}>
                    <Text strong>ROI</Text>
                    <PhotoView src={selectedAnomaly.roi_url}>
                      <img
                        src={selectedAnomaly.roi_url}
                        alt="roi"
                        style={{ width: "100%", cursor: "zoom-in", borderRadius: 6, objectFit: "cover" }}
                      />
                    </PhotoView>
                  </Col>
                )}
                {selectedAnomaly.heatmap_url && (
                  <Col span={6}>
                    <Text strong>Heatmap</Text>
                    <PhotoView src={selectedAnomaly.heatmap_url}>
                      <img
                        src={selectedAnomaly.heatmap_url}
                        alt="heatmap"
                        style={{ width: "100%", cursor: "zoom-in", borderRadius: 6, objectFit: "cover" }}
                      />
                    </PhotoView>
                  </Col>
                )}
                {selectedAnomaly.original_url && (
                  <Col span={6}>
                    <Text strong>Original</Text>
                    <PhotoView src={selectedAnomaly.original_url}>
                      <img
                        src={selectedAnomaly.original_url}
                        alt="original"
                        style={{ width: "100%", cursor: "zoom-in", borderRadius: 6, objectFit: "cover" }}
                      />
                    </PhotoView>
                  </Col>
                )}
              </PhotoProvider>
            </Row>

            <Button
              icon={<SearchOutlined />}
              onClick={() => handleSearchSimilar(selectedAnomaly.anomaly_id)}
              loading={searchingSimilar}
            >
              Find Similar
            </Button>

            {similarResults.length > 0 && (
              <div style={{ marginTop: 16 }}>
                <Text strong>Similar Anomalies ({similarResults.length})</Text>
                <Table
                  style={{ marginTop: 8 }}
                  dataSource={similarResults}
                  columns={[
                    {
                      title: "Anomaly ID",
                      dataIndex: "anomaly_id",
                      key: "id",
                      render: (id: string) => (
                        <Text code>{String(id).slice(0, 12)}...</Text>
                      ),
                    },
                    {
                      title: "Similarity",
                      dataIndex: "similarity",
                      key: "sim",
                      render: (s: number) => (
                        <Tag color={s > 0.9 ? "green" : "orange"}>
                          {(s * 100).toFixed(1)}%
                        </Tag>
                      ),
                    },
                  ]}
                  pagination={false}
                  size="small"
                  rowKey="anomaly_id"
                />
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
