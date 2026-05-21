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
    <Modal title="Evaluate Rules" open={open} onCancel={onClose} footer={null} width={650}>
      <Form form={form} layout="vertical" onFinish={onSubmit}>
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item name="camera_id" label="Camera ID" rules={[{ required: true }]}>
              <Input placeholder="e.g. left_top" />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="defect_type" label="Defect Type">
              <Select
                allowClear
                placeholder="Optional"
                options={DEFECT_TYPES as unknown as { value: string; label: string }[]}
              />
            </Form.Item>
          </Col>
        </Row>
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item name="anomaly_score" label="Anomaly Score">
              <InputNumber min={0} max={1} step={0.01} className="w-full" placeholder="0.85" />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="classifier_prediction" label="Classifier Prediction">
              <Select
                allowClear
                placeholder="Optional"
                options={[
                  { value: "real_defect", label: "Real Defect" },
                  { value: "false_alarm", label: "False Alarm" },
                ]}
              />
            </Form.Item>
          </Col>
        </Row>
        <Button type="primary" htmlType="submit" loading={loading} icon={<ThunderboltOutlined />}>
          Run Evaluation
        </Button>
      </Form>
    </Modal>
  );
}
