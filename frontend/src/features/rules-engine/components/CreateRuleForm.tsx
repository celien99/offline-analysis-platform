import type { FormInstance } from "antd";
import { Modal, Form, Input, Select, Row, Col, InputNumber } from "antd";
import { RULE_TYPE_OPTIONS } from "../../../lib/constants";

const { TextArea } = Input;

interface Props {
  form: FormInstance;
  open: boolean;
  submitting: boolean;
  onSubmit: (values: Record<string, unknown>) => void;
  onClose: () => void;
}

export default function CreateRuleForm({ form, open, submitting, onSubmit, onClose }: Props) {
  return (
    <Modal
      title="Create Rule"
      open={open}
      onCancel={onClose}
      onOk={() => form.submit()}
      confirmLoading={submitting}
      width={600}
    >
      <Form form={form} layout="vertical" onFinish={onSubmit}>
        <Form.Item name="name" label="Name" rules={[{ required: true }]}>
          <Input placeholder="e.g. Ignore reflection on left camera" />
        </Form.Item>
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item name="rule_type" label="Type" rules={[{ required: true }]}>
              <Select options={RULE_TYPE_OPTIONS as { value: string; label: string }[]} />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="priority" label="Priority" initialValue={0}>
              <InputNumber min={0} max={100} className="w-full" />
            </Form.Item>
          </Col>
        </Row>
        <Form.Item
          name="condition_json"
          label="Condition (JSON)"
          rules={[{ required: true }]}
          help='e.g. {"defect_type": "reflection", "min_score": 0.6}'
        >
          <TextArea rows={4} placeholder='{"defect_type": "reflection"}' />
        </Form.Item>
        <Form.Item name="description" label="Description">
          <TextArea rows={2} maxLength={500} />
        </Form.Item>
        <Form.Item name="camera_ids" label="Camera IDs (comma separated)">
          <Input placeholder="left_top,right_top (empty = all cameras)" />
        </Form.Item>
        <Form.Item name="knowledge_entry_id" label="Link to Knowledge Entry ID">
          <Input placeholder="Optional" />
        </Form.Item>
      </Form>
    </Modal>
  );
}
