import { useState } from "react";
import {
  Modal,
  Descriptions,
  Tag,
  Image,
  List,
  Card,
  Button,
  Space,
  message,
  Divider,
  Typography,
  Spin,
  Empty,
} from "antd";
import {
  ExperimentOutlined,
  BookOutlined,
  LinkOutlined,
} from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import type { ClusterDetail } from "../../../types";
import { useClusterAnomalies, useVLMAnalyzeCluster, useKnowledgeCreate } from "../../../hooks/queries";

const { Text, Paragraph } = Typography;

interface Props {
  cluster: ClusterDetail | null;
  open: boolean;
  onClose: () => void;
}

export default function ClusterDetailModal({ cluster, open, onClose }: Props) {
  const navigate = useNavigate();
  const [vlmResult, setVlmResult] = useState<Record<string, unknown> | null>(null);

  const { data: anomalies = [], isLoading: anomaliesLoading } = useClusterAnomalies(
    open ? cluster?.cluster_id ?? null : null,
  );

  const vlmMutation = useVLMAnalyzeCluster();
  const knowledgeMutation = useKnowledgeCreate();

  if (!cluster) {
    return (
      <Modal title="聚类详情" open={open} onCancel={onClose} footer={null} width={840}>
        <div className="flex items-center justify-center py-12">
          <Spin size="large" />
        </div>
      </Modal>
    );
  }

  const handleVLMAnalyze = async () => {
    try {
      await vlmMutation.mutateAsync(cluster.cluster_id);
      message.success("VLM 分析已触发，请稍后刷新查看结果");
    } catch {
      message.error("VLM 分析触发失败");
    }
  };

  const handleGenerateKnowledge = async () => {
    try {
      await knowledgeMutation.mutateAsync({
        title: `${cluster.defect_type || cluster.possible_type || "anomaly"} from ${cluster.cluster_id.slice(0, 8)}`,
        category: cluster.review_status === "real_defect" ? "defect" : "false_alarm",
        defect_type: cluster.defect_type || undefined,
        action: cluster.review_status === "real_defect" ? "NG" : "ignore",
        description: cluster.vlm_reason || `Cluster ${cluster.cluster_id} reviewed as ${cluster.review_status}`,
        cluster_id: cluster.cluster_id,
      });
      message.success("知识条目已创建");
    } catch {
      message.error("知识条目创建失败");
    }
  };

  const reviewColor = (s: string | null) => {
    if (s === "real_defect") return "red";
    if (s === "false_alarm") return "green";
    return "default";
  };

  return (
    <Modal
      title={
        <Space>
          Cluster {cluster.cluster_id.slice(0, 12)}...
          <Tag color={reviewColor(cluster.review_status)}>
            {cluster.review_status ?? cluster.status}
          </Tag>
        </Space>
      }
      open={open}
      onCancel={onClose}
      footer={
        <Space>
          <Button icon={<ExperimentOutlined />} onClick={handleVLMAnalyze} loading={vlmMutation.isPending}>
            VLM 分析
          </Button>
          <Button
            type="primary"
            icon={<BookOutlined />}
            onClick={handleGenerateKnowledge}
            loading={knowledgeMutation.isPending}
          >
            生成知识条目
          </Button>
        </Space>
      }
      width={900}
    >
      {/* 基本信息 */}
      <Descriptions column={3} bordered size="small">
        <Descriptions.Item label="样本数">{cluster.sample_count}</Descriptions.Item>
        <Descriptions.Item label="HDBSCAN 标签">{cluster.hdbscan_label}</Descriptions.Item>
        <Descriptions.Item label="置信度">
          {cluster.hdbscan_probability?.toFixed(3) ?? "-"}
        </Descriptions.Item>
        <Descriptions.Item label="缺陷类型">
          {cluster.defect_type ? <Tag color="purple">{cluster.defect_type}</Tag> : "-"}
        </Descriptions.Item>
        <Descriptions.Item label="状态">{cluster.status}</Descriptions.Item>
        <Descriptions.Item label="审核人">{cluster.reviewed_by ?? "-"}</Descriptions.Item>
      </Descriptions>

      {/* VLM 分析结果 */}
      {(cluster.vlm_analyzed_at || cluster.vlm_reason || cluster.vlm_suggestion) && (
        <>
          <Divider orientation="left" plain>
            <ExperimentOutlined /> VLM 分析
          </Divider>
          <Descriptions column={2} bordered size="small">
            <Descriptions.Item label="异常类型">
              <Tag color="orange">{cluster.vlm_anomaly_type ?? "-"}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="是否误报">
              <Tag color={cluster.vlm_is_false_alarm ? "green" : "red"}>
                {cluster.vlm_is_false_alarm ? "是" : cluster.vlm_is_false_alarm === false ? "否" : "-"}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="置信度">
              {cluster.vlm_confidence != null ? `${(cluster.vlm_confidence * 100).toFixed(1)}%` : "-"}
            </Descriptions.Item>
            <Descriptions.Item label="分析时间">
              {cluster.vlm_analyzed_at ? new Date(cluster.vlm_analyzed_at).toLocaleString() : "-"}
            </Descriptions.Item>
            {cluster.vlm_reason && (
              <Descriptions.Item label="原因" span={2}>
                <Text>{cluster.vlm_reason}</Text>
              </Descriptions.Item>
            )}
            {cluster.vlm_suggestion && (
              <Descriptions.Item label="建议" span={2}>
                <Text type="secondary">{cluster.vlm_suggestion}</Text>
              </Descriptions.Item>
            )}
          </Descriptions>
        </>
      )}

      {/* 代表图片 */}
      {cluster.representative_image_urls.length > 0 && (
        <>
          <Divider orientation="left" plain>代表图片</Divider>
          <Image.PreviewGroup>
            <Space wrap>
              {cluster.representative_image_urls.map((url, i) => (
                <Image
                  key={i}
                  src={url}
                  width={160}
                  height={120}
                  style={{ objectFit: "cover", borderRadius: 4 }}
                  fallback="data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTYwIiBoZWlnaHQ9IjEyMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZjBmMGYwIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGRvbWluYW50LWJhc2VsaW5lPSJtaWRkbGUiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGZpbGw9IiNjY2MiIGZvbnQtc2l6ZT0iMTIiPuWbvueJi+WKoOi9veWksei0pTwvdGV4dD48L3N2Zz4="
                />
              ))}
            </Space>
          </Image.PreviewGroup>
        </>
      )}

      {/* 关联 Anomalies */}
      <Divider orientation="left" plain>
        <LinkOutlined /> 关联 Anomalies
      </Divider>
      {anomaliesLoading ? (
        <Spin />
      ) : anomalies.length === 0 ? (
        <Empty description="暂无 anomaly 数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <List
          grid={{ gutter: 16, column: 2 }}
          dataSource={anomalies}
          renderItem={(a) => (
            <List.Item>
              <Card
                size="small"
                hoverable
                onClick={() => navigate(`/anomalies?anomaly_id=${a.anomaly_id}`)}
                styles={{ body: { padding: 8 } }}
              >
                <Space direction="vertical" size={2} style={{ width: "100%" }}>
                  <Space>
                    <Text code className="text-xs">{a.anomaly_id.slice(0, 12)}...</Text>
                    <Tag className="text-xs">{a.camera_id}</Tag>
                  </Space>
                  <Text className="text-xs" type="secondary">
                    分数: {a.anomaly_score?.toFixed(4) ?? "-"} | {a.status}
                  </Text>
                  {a.crop_url && (
                    <Image
                      src={a.crop_url}
                      width="100%"
                      height={100}
                      style={{ objectFit: "cover", borderRadius: 4 }}
                      fallback="data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHJlY3Qgd2lkdGg9IjEwMCUiIGhlaWdodD0iMTAwJSIgZmlsbD0iI2YwZjBmMCIvPjwvc3ZnPg=="
                    />
                  )}
                </Space>
              </Card>
            </List.Item>
          )}
        />
      )}
    </Modal>
  );
}
