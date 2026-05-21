import { useEffect, useState } from "react";
import { Card, Table, Button, Space, Input, Select, message } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import type { AnomalyRecord } from "../../types";
import { anomalyApi } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import { useAnomalyColumns } from "./components/AnomalyTable";
import AnomalyDetailModal from "./components/AnomalyDetailModal";

export default function AnomalyBrowser() {
  const [anomalies, setAnomalies] = useState<AnomalyRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [cameraFilter, setCameraFilter] = useState<string | undefined>();
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [selectedAnomaly, setSelectedAnomaly] = useState<AnomalyRecord | null>(null);
  const [detailVisible, setDetailVisible] = useState(false);

  const load = async (p = page) => {
    setLoading(true);
    try {
      setAnomalies(
        await anomalyApi.list({
          page: p,
          page_size: 20,
          camera_id: cameraFilter,
          status: statusFilter,
        }),
      );
    } catch {
      message.error("Failed to load anomalies");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [page, cameraFilter, statusFilter]);

  const handleViewDetail = async (anomalyId: string) => {
    try {
      setSelectedAnomaly(await anomalyApi.detail(anomalyId));
      setDetailVisible(true);
    } catch {
      message.error("Failed to load anomaly detail");
    }
  };

  const handleReprocess = async (anomalyId: string) => {
    try {
      await anomalyApi.reprocess(anomalyId);
      message.success("Anomaly queued for reprocessing");
      load();
    } catch {
      message.error("Reprocess failed");
    }
  };

  const columns = useAnomalyColumns({ onViewDetail: handleViewDetail, onReprocess: handleReprocess });

  return (
    <div>
      <PageHeader
        title="Anomaly Browser"
        extra={
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
            <Button icon={<ReloadOutlined />} onClick={() => load()}>Refresh</Button>
          </Space>
        }
      />

      <Card>
        <Table
          columns={columns}
          dataSource={anomalies}
          rowKey="anomaly_id"
          loading={loading}
          pagination={{ current: page, pageSize: 20, onChange: setPage }}
        />
      </Card>

      <AnomalyDetailModal anomaly={selectedAnomaly} open={detailVisible} onClose={() => setDetailVisible(false)} />
    </div>
  );
}
