import type { FormInstance } from "antd";
import { Modal, Form, Input, Select, Row, Col, InputNumber } from "antd";
import { RULE_TYPE_OPTIONS } from "../../../lib/constants";
import RuleConditionBuilder from "./RuleConditionBuilder";

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
      title="创建规则"
      open={open}
      onCancel={onClose}
      onOk={() => form.submit()}
      confirmLoading={submitting}
      width={640}
    >
      <Form form={form} layout="vertical" onFinish={onSubmit}>
        <Row gutter={16}>
          <Col span={16}>
            <Form.Item name="name" label="名称" rules={[{ required: true }]}>
              <Input placeholder="例如: 忽略左相机反光" />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item name="priority" label="优先级" initialValue={0}>
              <InputNumber min={0} max={100} className="w-full" />
            </Form.Item>
          </Col>
        </Row>
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item name="rule_type" label="类型" rules={[{ required: true }]}>
              <Select options={RULE_TYPE_OPTIONS as { value: string; label: string }[]} />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="camera_ids" label="相机ID">
              <Input placeholder="逗号分隔，留空=所有相机" />
            </Form.Item>
          </Col>
        </Row>
        <Form.Item label="条件" required>
          <Form.Item noStyle name="conditions" initialValue={[{ field: "camera_id", operator: "=", value: "" }]}>
            <RuleConditionBuilder />
          </Form.Item>
        </Form.Item>
        <Form.Item name="description" label="描述">
          <Input.TextArea rows={2} maxLength={500} />
        </Form.Item>
      </Form>
    </Modal>
  );
}
