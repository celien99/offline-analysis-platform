import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Card, Table, Button, Space, Input, Select, message } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import type { AnomalyRecord } from "../../types";
import { anomalyApi } from "../../api";
import { useAnomalyList, useAnomalyReprocess } from "../../hooks/queries";
import PageHeader from "../../components/ui/PageHeader";
import { useAnomalyColumns } from "./components/AnomalyTable";
import AnomalyDetailModal from "./components/AnomalyDetailModal";

export default function AnomalyBrowser() {
  const [searchParams] = useSearchParams();
  const urlAnomalyId = searchParams.get("anomaly_id");

  const [page, setPage] = useState(1);
  const [cameraInput, setCameraInput] = useState("");
  const [cameraFilter, setCameraFilter] = useState<string | undefined>();
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [selectedAnomaly, setSelectedAnomaly] = useState<AnomalyRecord | null>(null);
  const [detailVisible, setDetailVisible] = useState(false);

  // URL 携带 anomaly_id 时自动加载详情
  useEffect(() => {
    if (urlAnomalyId) {
      anomalyApi.detail(urlAnomalyId).then(setSelectedAnomaly).catch(() => {});
      setDetailVisible(true);
    }
  }, [urlAnomalyId]);

  useEffect(() => {
    const timer = setTimeout(() => {
      setCameraFilter(cameraInput || undefined);
    }, 400);
    return () => clearTimeout(timer);
  }, [cameraInput]);

  const { data, isLoading, refetch } = useAnomalyList({
    page,
    camera_id: cameraFilter,
    status: statusFilter,
  });
  const anomalies = data?.items ?? [];
  const total = data?.total ?? 0;

  const reprocessMutation = useAnomalyReprocess();

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
      await reprocessMutation.mutateAsync(anomalyId);
      message.success("Anomaly queued for reprocessing");
    } catch {
      message.error("Reprocess failed");
    }
  };

  const handleDelete = async (anomalyId: string) => {
    try {
      await anomalyApi.delete(anomalyId);
      message.success("Anomaly deleted");
      refetch();
    } catch {
      message.error("Delete failed");
    }
  };

  const columns = useAnomalyColumns({
    onViewDetail: handleViewDetail,
    onReprocess: handleReprocess,
    onDelete: handleDelete,
  });

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
              value={cameraInput}
              onChange={(e) => setCameraInput(e.target.value)}
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
            <Button icon={<ReloadOutlined />} onClick={() => refetch()}>Refresh</Button>
          </Space>
        }
      />

      <Card>
        <Table
          columns={columns}
          dataSource={anomalies}
          rowKey="anomaly_id"
          loading={isLoading}
          pagination={{ current: page, pageSize: 20, total, onChange: setPage }}
        />
      </Card>

      <AnomalyDetailModal anomaly={selectedAnomaly} open={detailVisible} onClose={() => setDetailVisible(false)} />
    </div>
  );
}
