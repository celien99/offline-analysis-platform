import type { FormInstance } from "antd";
import { Modal, Form, Input, Select, Row, Col } from "antd";
import { CATEGORY_OPTIONS, DEFECT_TYPES, ACTION_OPTIONS } from "../../../lib/constants";

const { TextArea } = Input;

interface Props {
  form: FormInstance;
  open: boolean;
  submitting: boolean;
  onSubmit: (values: Record<string, unknown>) => void;
  onClose: () => void;
}

export default function CreateKnowledgeForm({ form, open, submitting, onSubmit, onClose }: Props) {
  return (
    <Modal
      title="Create Knowledge Entry"
      open={open}
      onCancel={onClose}
      onOk={() => form.submit()}
      confirmLoading={submitting}
      width={600}
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
        <Form.Item name="cluster_id" label="Cluster ID">
          <Input placeholder="Optional: link to a cluster" />
        </Form.Item>
        <Form.Item name="camera_ids" label="Camera IDs (comma separated)">
          <Input placeholder="e.g. left_top, right_bottom" />
        </Form.Item>
      </Form>
    </Modal>
  );
}
