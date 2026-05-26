import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Card, Table, Button, Input, Space, Tag, Modal, Descriptions, message } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import type { ClusterSummary, DualTrackComparisonResult } from "../../types";
import { useClusterList, useClusterDetail, useClusterReview, useDualTrackComparison } from "../../hooks/queries";
import PageHeader from "../../components/ui/PageHeader";
import { useClusterColumns } from "./components/ClusterTable";
import ClusterDetailModal from "./components/ClusterDetailModal";
import ReviewModal from "./components/ReviewModal";

export default function ClusterReview() {
  const [searchParams] = useSearchParams();
  const urlClusterId = searchParams.get("cluster_id");

  const [page, setPage] = useState(1);
  const [selectedClusterId, setSelectedClusterId] = useState<string | null>(null);
  const [detailVisible, setDetailVisible] = useState(false);
  const [reviewVisible, setReviewVisible] = useState(false);
  const [reviewAction, setReviewAction] = useState<"confirm_defect" | "mark_false_alarm">("confirm_defect");
  const [defectType, setDefectType] = useState<string | undefined>();
  const [comment, setComment] = useState("");
  const [seatModelFilter, setSeatModelFilter] = useState<string | undefined>();
  const [cameraFilter, setCameraFilter] = useState<string | undefined>();
  const [regionFilter, setRegionFilter] = useState<string | undefined>();
  const [compareVisible, setCompareVisible] = useState(false);

  // 双轨对比
  const { data: compareData, refetch: refetchCompare, isFetching: compareLoading } = useDualTrackComparison({
    seat_model_id: seatModelFilter,
    camera_id: cameraFilter,
    region_id: regionFilter,
  });

  // URL 携带 cluster_id 时自动打开详情
  useEffect(() => {
    if (urlClusterId) {
      setSelectedClusterId(urlClusterId);
      setDetailVisible(true);
    }
  }, [urlClusterId]);

  const { data: listData, isLoading, refetch } = useClusterList(page, {
    seatModelId: seatModelFilter,
    cameraId: cameraFilter,
    regionId: regionFilter,
  });
  const { data: selectedCluster } = useClusterDetail(selectedClusterId);
  const reviewMutation = useClusterReview();

  const handleViewDetail = (clusterId: string) => {
    setSelectedClusterId(clusterId);
    setDetailVisible(true);
  };

  const handleReview = (cluster: ClusterSummary, action: "confirm_defect" | "mark_false_alarm") => {
    setSelectedClusterId(cluster.cluster_id);
    setReviewAction(action);
    setDefectType(undefined);
    setComment("");
    setReviewVisible(true);
  };

  const handleSubmitReview = async () => {
    if (!selectedClusterId) return;
    try {
      await reviewMutation.mutateAsync({
        cluster_id: selectedClusterId,
        reviewer: "engineer",
        action: reviewAction,
        defect_type: defectType as "wrinkle" | "scratch" | "reflection" | "stain" | "seam_shift" | undefined,
        comment: comment || undefined,
      });
      message.success("审核已提交");
      setReviewVisible(false);
    } catch {
      message.error("提交审核失败");
    }
  };

  const columns = useClusterColumns({ clusters: listData?.clusters ?? [], onViewDetail: handleViewDetail, onReview: handleReview });

  return (
    <div>
      <PageHeader
        title="聚类审核"
        extra={
          <Space>
            <Input
              placeholder="座椅型号ID"
              allowClear
              style={{ width: 150 }}
              value={seatModelFilter}
              onChange={(e) => setSeatModelFilter(e.target.value || undefined)}
            />
            <Input
              placeholder="相机ID"
              allowClear
              style={{ width: 120 }}
              value={cameraFilter}
              onChange={(e) => setCameraFilter(e.target.value || undefined)}
            />
            <Input
              placeholder="区域ID"
              allowClear
              style={{ width: 120 }}
              value={regionFilter}
              onChange={(e) => setRegionFilter(e.target.value || undefined)}
            />
            <Button icon={<ReloadOutlined />} onClick={() => refetch()}>刷新</Button>
            <Button onClick={() => { setCompareVisible(true); refetchCompare(); }}>双轨对比</Button>
          </Space>
        }
      />

      <Card>
        <Table
          columns={columns}
          dataSource={listData?.clusters ?? []}
          rowKey="cluster_id"
          loading={isLoading}
          pagination={{
            current: page,
            total: listData?.total ?? 0,
            pageSize: 20,
            onChange: setPage,
            showTotal: (t) => `共 ${t} 个聚类`,
          }}
        />
      </Card>

      <ClusterDetailModal cluster={selectedCluster ?? null} open={detailVisible} onClose={() => setDetailVisible(false)} />

      <ReviewModal
        cluster={selectedCluster ?? null}
        action={reviewAction}
        defectType={defectType}
        comment={comment}
        submitting={reviewMutation.isPending}
        open={reviewVisible}
        onDefectTypeChange={setDefectType}
        onCommentChange={setComment}
        onSubmit={handleSubmitReview}
        onClose={() => setReviewVisible(false)}
      />

      {/* ── 双轨对比 Modal ── */}
      <Modal
        title="双轨聚类对比 (Raw vs Refined Embedding)"
        open={compareVisible}
        onCancel={() => setCompareVisible(false)}
        footer={null}
        width={640}
      >
        {compareLoading ? (
          <p>加载中...</p>
        ) : compareData ? (
          <div>
            <p style={{ fontWeight: "bold", marginBottom: 16 }}>
              {compareData.recommendation}
            </p>
            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label="指标"> </Descriptions.Item>
              <Descriptions.Item label="Raw">
                <Tag color="blue">原始</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Refined">
                <Tag color="green">精化</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="样本数">
                {compareData.raw?.sample_count ?? "-"}
              </Descriptions.Item>
              <Descriptions.Item label="样本数">
                {compareData.refined?.sample_count ?? "-"}
              </Descriptions.Item>
              <Descriptions.Item label="簇数量">
                {compareData.raw?.cluster_count ?? "-"}
              </Descriptions.Item>
              <Descriptions.Item label="簇数量">
                {compareData.refined?.cluster_count ?? "-"}
              </Descriptions.Item>
              <Descriptions.Item label="噪声率">
                {compareData.raw ? (compareData.raw.noise_rate * 100).toFixed(1) + "%" : "-"}
              </Descriptions.Item>
              <Descriptions.Item label="噪声率">
                {compareData.refined ? (compareData.refined.noise_rate * 100).toFixed(1) + "%" : "-"}
              </Descriptions.Item>
              <Descriptions.Item label="最大簇占比">
                {compareData.raw ? (compareData.raw.max_cluster_ratio * 100).toFixed(1) + "%" : "-"}
              </Descriptions.Item>
              <Descriptions.Item label="最大簇占比">
                {compareData.refined ? (compareData.refined.max_cluster_ratio * 100).toFixed(1) + "%" : "-"}
              </Descriptions.Item>
              <Descriptions.Item label="平均簇大小">
                {compareData.raw?.avg_cluster_size.toFixed(1) ?? "-"}
              </Descriptions.Item>
              <Descriptions.Item label="平均簇大小">
                {compareData.refined?.avg_cluster_size.toFixed(1) ?? "-"}
              </Descriptions.Item>
            </Descriptions>
          </div>
        ) : (
          <p>选择筛选条件后点击"双轨对比"按钮查看聚类质量对比</p>
        )}
      </Modal>
    </div>
  );
}
