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
    undefined,
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
    label: `${c.name || c.cluster_id.slice(0, 8)} (${c.sample_count} 个样本, ${c.review_status || c.status})`,
  }));

  return (
    <Modal
      title="创建知识条目"
      open={open}
      onCancel={onClose}
      onOk={() => form.submit()}
      confirmLoading={submitting}
      width={600}
      afterOpenChange={(visible) => { if (visible) handleOpen(); }}
    >
      <Form form={form} layout="vertical" onFinish={onSubmit}>
        <Form.Item name="title" label="标题" rules={[{ required: true }]}>
          <Input maxLength={256} placeholder="例如: 左座椅边缘反光模式" />
        </Form.Item>
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item name="category" label="类别" rules={[{ required: true }]}>
              <Select options={CATEGORY_OPTIONS as { value: string; label: string }[]} placeholder="选择类别" />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="defect_type" label="缺陷类型">
              <Select options={DEFECT_TYPES as { value: string; label: string }[]} placeholder="可选" allowClear />
            </Form.Item>
          </Col>
        </Row>
        <Form.Item name="action" label="动作" rules={[{ required: true }]}>
          <Select options={ACTION_OPTIONS as { value: string; label: string }[]} placeholder="选择动作" />
        </Form.Item>
        <Form.Item name="description" label="描述">
          <TextArea rows={3} maxLength={2000} placeholder="描述缺陷模式..." />
        </Form.Item>
        <Form.Item name="cluster_id" label="聚类">
          <Select
            options={clusterOptions}
            placeholder={clustersLoading ? "加载聚类中..." : "选择聚类 (可选)"}
            allowClear
            showSearch
            filterOption={(input, option) =>
              (option?.label as string)?.toLowerCase().includes(input.toLowerCase()) ?? false
            }
            notFoundContent={clustersLoading ? <Spin size="small" /> : null}
          />
        </Form.Item>
        <Form.Item name="camera_ids" label="相机ID (逗号分隔)">
          <Input placeholder="例如: left_top, right_bottom" />
        </Form.Item>
      </Form>
    </Modal>
  );
}
