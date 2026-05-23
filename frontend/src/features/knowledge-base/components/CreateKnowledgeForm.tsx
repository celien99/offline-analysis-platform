import type { FormInstance } from "antd";
import { Modal, Form, Input, Select, Row, Col, Spin } from "antd";
import { CATEGORY_OPTIONS, DEFECT_TYPES, ACTION_OPTIONS } from "../../../lib/constants";
import { useClusterList } from "../../../hooks/queries";

const { TextArea } = Input;

interface Props {
  form: FormInstance;
  open: boolean;
  submitting: boolean;
  /** 如果从 cluster 页面跳转，预填 cluster_id。 */
  initialClusterId?: string;
  onSubmit: (values: Record<string, unknown>) => void;
  onClose: () => void;
}

export default function CreateKnowledgeForm({ form, open, submitting, initialClusterId, onSubmit, onClose }: Props) {
  const { data: clusterData, isLoading: clustersLoading } = useClusterList(
    1,
    open, // 只在弹窗打开时请求
  );

  // 弹窗打开时预填 cluster_id
  const handleOpen = () => {
    if (initialClusterId) {
      form.setFieldsValue({ cluster_id: initialClusterId });
    }
  };

  const clusterOptions = (clusterData?.clusters ?? []).map((c) => ({
    value: c.cluster_id,
    label: `${c.name || c.cluster_id.slice(0, 8)} (${c.sample_count} samples, ${c.review_status || c.status})`,
  }));

  return (
    <Modal
      title="Create Knowledge Entry"
      open={open}
      onCancel={onClose}
      onOk={() => form.submit()}
      confirmLoading={submitting}
      width={600}
      afterOpenChange={(visible) => { if (visible) handleOpen(); }}
    >
      <Form form={form} layout="vertical" onFinish={onSubmit}>
        <Form.Item name="title" label="Title" rules={[{ required: true }]}>
          <Input maxLength={256} placeholder="e.g. Reflection pattern on left seat edge" />
        </Form.Item>
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item name="category" label="Category" rules={[{ required: true }]}>
              <Select options={CATEGORY_OPTIONS as { value: string; label: string }[]} placeholder="Select category" />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="defect_type" label="Defect Type">
              <Select options={DEFECT_TYPES as { value: string; label: string }[]} placeholder="Optional" allowClear />
            </Form.Item>
          </Col>
        </Row>
        <Form.Item name="action" label="Action" rules={[{ required: true }]}>
          <Select options={ACTION_OPTIONS as { value: string; label: string }[]} placeholder="Select action" />
        </Form.Item>
        <Form.Item name="description" label="Description">
          <TextArea rows={3} maxLength={2000} placeholder="Describe the defect pattern..." />
        </Form.Item>
        <Form.Item name="cluster_id" label="Cluster">
          <Select
            options={clusterOptions}
            placeholder={clustersLoading ? "Loading clusters..." : "Select a cluster (optional)"}
            allowClear
            showSearch
            filterOption={(input, option) =>
              (option?.label as string)?.toLowerCase().includes(input.toLowerCase()) ?? false
            }
            notFoundContent={clustersLoading ? <Spin size="small" /> : null}
          />
        </Form.Item>
        <Form.Item name="camera_ids" label="Camera IDs (comma separated)">
          <Input placeholder="e.g. left_top, right_bottom" />
        </Form.Item>
      </Form>
    </Modal>
  );
}
