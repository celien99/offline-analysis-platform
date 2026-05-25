import type { FormInstance } from "antd";
import { Modal, Form, Input, Select, Row, Col, InputNumber, Button } from "antd";
import { ThunderboltOutlined } from "@ant-design/icons";
import { DEFECT_TYPES } from "../../../lib/constants";

interface Props {
  form: FormInstance;
  open: boolean;
  loading: boolean;
  onSubmit: (values: Record<string, unknown>) => void;
  onClose: () => void;
}

export default function EvaluateRuleForm({ form, open, loading, onSubmit, onClose }: Props) {
  return (
    <Modal title="评估规则" open={open} onCancel={onClose} footer={null} width={650}>
      <Form form={form} layout="vertical" onFinish={onSubmit}>
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item name="camera_id" label="相机ID" rules={[{ required: true }]}>
              <Input placeholder="e.g. left_top" />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="defect_type" label="缺陷类型">
              <Select
                allowClear
                placeholder="可选"
                options={DEFECT_TYPES as unknown as { value: string; label: string }[]}
              />
            </Form.Item>
          </Col>
        </Row>
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item name="anomaly_score" label="异常分数">
              <InputNumber min={0} max={1} step={0.01} className="w-full" placeholder="0.85" />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="classifier_prediction" label="分类器预测">
              <Select
                allowClear
                placeholder="可选"
                options={[
                  { value: "real_defect", label: "真实缺陷" },
                  { value: "false_alarm", label: "误报" },
                ]}
              />
            </Form.Item>
          </Col>
        </Row>
        <Button type="primary" htmlType="submit" loading={loading} icon={<ThunderboltOutlined />}>
          运行评估
        </Button>
      </Form>
    </Modal>
  );
}
