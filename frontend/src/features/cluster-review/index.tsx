import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Card, Table, Button, message } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import type { ClusterSummary } from "../../types";
import { useClusterList, useClusterDetail, useClusterReview } from "../../hooks/queries";
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

  // URL 携带 cluster_id 时自动打开详情
  useEffect(() => {
    if (urlClusterId) {
      setSelectedClusterId(urlClusterId);
      setDetailVisible(true);
    }
  }, [urlClusterId]);

  const { data: listData, isLoading, refetch } = useClusterList(page);
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
      message.success("Review submitted");
      setReviewVisible(false);
    } catch {
      message.error("Failed to submit review");
    }
  };

  const columns = useClusterColumns({ clusters: listData?.clusters ?? [], onViewDetail: handleViewDetail, onReview: handleReview });

  return (
    <div>
      <PageHeader
        title="Cluster Review"
        extra={<Button icon={<ReloadOutlined />} onClick={() => refetch()}>Refresh</Button>}
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
            showTotal: (t) => `Total ${t} clusters`,
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
    </div>
  );
}
