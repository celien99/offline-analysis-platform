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
      title="创建规则"
      open={open}
      onCancel={onClose}
      onOk={() => form.submit()}
      confirmLoading={submitting}
      width={600}
    >
      <Form form={form} layout="vertical" onFinish={onSubmit}>
        <Form.Item name="name" label="名称" rules={[{ required: true }]}>
          <Input placeholder="例如: 忽略左相机反光" />
        </Form.Item>
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item name="rule_type" label="类型" rules={[{ required: true }]}>
              <Select options={RULE_TYPE_OPTIONS as { value: string; label: string }[]} />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="priority" label="优先级" initialValue={0}>
              <InputNumber min={0} max={100} className="w-full" />
            </Form.Item>
          </Col>
        </Row>
        <Form.Item
          name="condition_json"
          label="条件 (JSON)"
          rules={[{ required: true }]}
          help='例如: {"defect_type": "reflection", "min_score": 0.6}'
        >
          <TextArea rows={4} placeholder='{"defect_type": "reflection"}' />
        </Form.Item>
        <Form.Item name="description" label="描述">
          <TextArea rows={2} maxLength={500} />
        </Form.Item>
        <Form.Item name="camera_ids" label="相机ID (逗号分隔)">
          <Input placeholder="left_top,right_top (留空 = 所有相机)" />
        </Form.Item>
        <Form.Item name="knowledge_entry_id" label="关联知识条目ID">
          <Input placeholder="可选" />
        </Form.Item>
      </Form>
    </Modal>
  );
}
