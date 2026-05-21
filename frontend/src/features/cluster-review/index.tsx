import { useEffect, useState } from "react";
import { Card, Table, Button, message } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import type { ClusterSummary, ClusterDetail } from "../../types";
import { clusterApi } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import { useClusterColumns } from "./components/ClusterTable";
import ClusterDetailModal from "./components/ClusterDetailModal";
import ReviewModal from "./components/ReviewModal";

export default function ClusterReview() {
  const [clusters, setClusters] = useState<ClusterSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [selectedCluster, setSelectedCluster] = useState<ClusterDetail | null>(null);
  const [detailVisible, setDetailVisible] = useState(false);
  const [reviewVisible, setReviewVisible] = useState(false);
  const [reviewAction, setReviewAction] = useState<"confirm_defect" | "mark_false_alarm">("confirm_defect");
  const [defectType, setDefectType] = useState<string | undefined>();
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const load = async (p = page) => {
    setLoading(true);
    try {
      const data = await clusterApi.list(p, 20);
      setClusters(data.clusters);
      setTotal(data.total);
    } catch {
      message.error("Failed to load clusters");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [page]);

  const handleViewDetail = async (clusterId: string) => {
    try {
      setSelectedCluster(await clusterApi.detail(clusterId));
      setDetailVisible(true);
    } catch {
      message.error("Failed to load cluster detail");
    }
  };

  const handleReview = (cluster: ClusterSummary, action: "confirm_defect" | "mark_false_alarm") => {
    setSelectedCluster(cluster as ClusterDetail);
    setReviewAction(action);
    setDefectType(undefined);
    setComment("");
    setReviewVisible(true);
  };

  const handleSubmitReview = async () => {
    if (!selectedCluster) return;
    setSubmitting(true);
    try {
      await clusterApi.review({
        cluster_id: selectedCluster.cluster_id,
        reviewer: "engineer",
        action: reviewAction,
        defect_type: defectType as "wrinkle" | "scratch" | "reflection" | "stain" | "seam_shift" | undefined,
        comment: comment || undefined,
      });
      message.success("Review submitted");
      setReviewVisible(false);
      load();
    } catch {
      message.error("Failed to submit review");
    } finally {
      setSubmitting(false);
    }
  };

  const columns = useClusterColumns({ clusters, onViewDetail: handleViewDetail, onReview: handleReview });

  return (
    <div>
      <PageHeader
        title="Cluster Review"
        extra={<Button icon={<ReloadOutlined />} onClick={() => load()}>Refresh</Button>}
      />

      <Card>
        <Table
          columns={columns}
          dataSource={clusters}
          rowKey="cluster_id"
          loading={loading}
          pagination={{
            current: page,
            total,
            pageSize: 20,
            onChange: setPage,
            showTotal: (t) => `Total ${t} clusters`,
          }}
        />
      </Card>

      <ClusterDetailModal cluster={selectedCluster} open={detailVisible} onClose={() => setDetailVisible(false)} />

      <ReviewModal
        cluster={selectedCluster}
        action={reviewAction}
        defectType={defectType}
        comment={comment}
        submitting={submitting}
        open={reviewVisible}
        onDefectTypeChange={setDefectType}
        onCommentChange={setComment}
        onSubmit={handleSubmitReview}
        onClose={() => setReviewVisible(false)}
      />
    </div>
  );
}
