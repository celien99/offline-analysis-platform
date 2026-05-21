import { useEffect, useState } from "react";
import {
  Card,
  Table,
  Tag,
  Button,
  Space,
  Modal,
  Descriptions,
  Select,
  Input,
  message,
  Row,
  Col,
  Badge,
  Typography,
} from "antd";
import {
  CheckOutlined,
  CloseOutlined,
  ReloadOutlined,
  EyeOutlined,
} from "@ant-design/icons";
import type { ClusterSummary, ClusterDetail } from "../types";
import { fetchClusters, fetchClusterDetail, submitReview } from "../api/client";

const { TextArea } = Input;
const { Text } = Typography;

const DEFECT_TYPES = [
  { value: "wrinkle", label: "Wrinkle" },
  { value: "scratch", label: "Scratch" },
  { value: "reflection", label: "Reflection" },
  { value: "stain", label: "Stain" },
  { value: "seam_shift", label: "Seam Shift" },
];

export default function ClusterReview() {
  const [clusters, setClusters] = useState<ClusterSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [selectedCluster, setSelectedCluster] = useState<ClusterDetail | null>(
    null
  );
  const [detailVisible, setDetailVisible] = useState(false);
  const [reviewVisible, setReviewVisible] = useState(false);
  const [reviewAction, setReviewAction] = useState<
    "confirm_defect" | "mark_false_alarm"
  >("confirm_defect");
  const [defectType, setDefectType] = useState<string | undefined>();
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const loadClusters = async (p = page) => {
    setLoading(true);
    try {
      const data = await fetchClusters(p, 20);
      setClusters(data.clusters);
      setTotal(data.total);
    } catch {
      message.error("Failed to load clusters");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadClusters();
  }, [page]);

  const handleViewDetail = async (clusterId: string) => {
    try {
      const detail = await fetchClusterDetail(clusterId);
      setSelectedCluster(detail);
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
      await submitReview({
        cluster_id: selectedCluster.cluster_id,
        reviewer: "engineer",
        action: reviewAction,
        defect_type: defectType as
          | "wrinkle"
          | "scratch"
          | "reflection"
          | "stain"
          | "seam_shift"
          | undefined,
        comment: comment || undefined,
      });
      message.success("Review submitted");
      setReviewVisible(false);
      loadClusters();
    } catch {
      message.error("Failed to submit review");
    } finally {
      setSubmitting(false);
    }
  };

  const columns = [
    {
      title: "Cluster",
      dataIndex: "name",
      key: "name",
      render: (_: string, record: ClusterSummary) => (
        <Space>
          <Badge
            status={
              record.review_status === "real_defect"
                ? "error"
                : record.review_status === "false_alarm"
                ? "success"
                : "processing"
            }
          />
          <Text strong>{record.name || `Cluster #${record.cluster_id.slice(0, 8)}`}</Text>
        </Space>
      ),
    },
    {
      title: "Samples",
      dataIndex: "sample_count",
      key: "sample_count",
      sorter: (a: ClusterSummary, b: ClusterSummary) =>
        a.sample_count - b.sample_count,
    },
    {
      title: "Possible Type",
      dataIndex: "possible_type",
      key: "possible_type",
      render: (t: string | null) => (
        <Tag color="blue">{t || "unknown"}</Tag>
      ),
    },
    {
      title: "Review Status",
      dataIndex: "review_status",
      key: "review_status",
      render: (s: string | null) => {
        const colorMap: Record<string, string> = {
          real_defect: "red",
          false_alarm: "green",
        };
        return <Tag color={colorMap[s || ""] || "orange"}>{s || "pending"}</Tag>;
      },
    },
    {
      title: "Defect Type",
      dataIndex: "defect_type",
      key: "defect_type",
      render: (t: string | null) => (
        <Tag color="purple">{t || "-"}</Tag>
      ),
    },
    {
      title: "Actions",
      key: "actions",
      width: 320,
      render: (_: unknown, record: ClusterSummary) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleViewDetail(record.cluster_id)}
          >
            Detail
          </Button>
          {record.status === "pending_review" && (
            <>
              <Button
                type="primary"
                size="small"
                icon={<CheckOutlined />}
                onClick={() => handleReview(record, "confirm_defect")}
              >
                Confirm
              </Button>
              <Button
                danger
                size="small"
                icon={<CloseOutlined />}
                onClick={() => handleReview(record, "mark_false_alarm")}
              >
                False Alarm
              </Button>
            </>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <h2>Cluster Review</h2>
        </Col>
        <Col>
          <Button icon={<ReloadOutlined />} onClick={() => loadClusters()}>
            Refresh
          </Button>
        </Col>
      </Row>

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

      <Modal
        title="Cluster Detail"
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={null}
        width={800}
      >
        {selectedCluster && (
          <Descriptions column={2} bordered size="small">
            <Descriptions.Item label="Cluster ID">
              {selectedCluster.cluster_id}
            </Descriptions.Item>
            <Descriptions.Item label="Samples">
              {selectedCluster.sample_count}
            </Descriptions.Item>
            <Descriptions.Item label="HDBSCAN Label">
              {selectedCluster.hdbscan_label}
            </Descriptions.Item>
            <Descriptions.Item label="Probability">
              {selectedCluster.hdbscan_probability?.toFixed(3) ?? "-"}
            </Descriptions.Item>
            <Descriptions.Item label="Status">
              {selectedCluster.status}
            </Descriptions.Item>
            <Descriptions.Item label="Defect Type">
              {selectedCluster.defect_type || "-"}
            </Descriptions.Item>
          </Descriptions>
        )}
      </Modal>

      <Modal
        title={
          reviewAction === "confirm_defect"
            ? "Confirm as Real Defect"
            : "Mark as False Alarm"
        }
        open={reviewVisible}
        onOk={handleSubmitReview}
        onCancel={() => setReviewVisible(false)}
        confirmLoading={submitting}
      >
        {reviewAction === "confirm_defect" && (
          <div style={{ marginBottom: 16 }}>
            <Text strong>Defect Type:</Text>
            <Select
              style={{ width: "100%", marginTop: 8 }}
              placeholder="Select defect type"
              options={DEFECT_TYPES}
              value={defectType}
              onChange={setDefectType}
              allowClear
            />
          </div>
        )}
        <div>
          <Text strong>Comment:</Text>
          <TextArea
            style={{ marginTop: 8 }}
            rows={3}
            placeholder="Optional review comment..."
            value={comment}
            onChange={(e) => setComment(e.target.value)}
          />
        </div>
      </Modal>
    </div>
  );
}
