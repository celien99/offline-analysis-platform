import { useEffect, useState } from "react";
import {
  Card,
  Table,
  Tag,
  Button,
  Space,
  Row,
  Col,
  Input,
  Select,
  Modal,
  Form,
  message,
  Popconfirm,
  Switch,
  Typography,
  Descriptions,
  InputNumber,
} from "antd";
import {
  PlusOutlined,
  ReloadOutlined,
  DeleteOutlined,
  PlayCircleOutlined,
  ThunderboltOutlined,
  BookOutlined,
} from "@ant-design/icons";
import axios from "axios";

const { Text, Paragraph } = Typography;
const { TextArea } = Input;

interface Rule {
  rule_id: string;
  name: string;
  rule_type: string;
  priority: number;
  enabled: boolean;
  description: string | null;
  created_at: string;
}

interface EvalResult {
  action: string;
  matched_rules: { rule_id: string; name: string; type: string; priority: number }[];
  rule_count: number;
}

export default function RulesManagement() {
  const [rules, setRules] = useState<Rule[]>([]);
  const [loading, setLoading] = useState(false);
  const [typeFilter, setTypeFilter] = useState<string | undefined>();
  const [createVisible, setCreateVisible] = useState(false);
  const [evalVisible, setEvalVisible] = useState(false);
  const [evalResult, setEvalResult] = useState<EvalResult | null>(null);
  const [evalLoading, setEvalLoading] = useState(false);
  const [genFromKbVisible, setGenFromKbVisible] = useState(false);
  const [form] = Form.useForm();
  const [evalForm] = Form.useForm();
  const [kbForm] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);

  const loadRules = async () => {
    setLoading(true);
    try {
      const { data } = await axios.get("/api/rules", {
        params: { rule_type: typeFilter, page_size: 200 },
      });
      setRules(data);
    } catch {
      message.error("Failed to load rules");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRules();
  }, [typeFilter]);

  const handleCreate = async (values: Record<string, unknown>) => {
    setSubmitting(true);
    try {
      let conditionJson = "{}";
      try {
        JSON.parse(values.condition_json as string);
        conditionJson = values.condition_json as string;
      } catch {
        message.error("Invalid JSON in condition");
        setSubmitting(false);
        return;
      }
      await axios.post("/api/rules", null, {
        params: {
          name: values.name,
          rule_type: values.rule_type,
          condition_json: conditionJson,
          priority: values.priority,
          description: values.description,
          camera_ids: values.camera_ids || undefined,
          knowledge_entry_id: values.knowledge_entry_id || undefined,
        },
      });
      message.success("Rule created");
      setCreateVisible(false);
      form.resetFields();
      loadRules();
    } catch {
      message.error("Failed to create rule");
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggle = async (ruleId: string, enabled: boolean) => {
    try {
      await axios.post(`/api/rules/${ruleId}/toggle?enabled=${enabled}`);
      message.success(`Rule ${enabled ? "enabled" : "disabled"}`);
      loadRules();
    } catch {
      message.error("Failed to toggle rule");
    }
  };

  const handleDelete = async (ruleId: string) => {
    try {
      await axios.delete(`/api/rules/${ruleId}`);
      message.success("Rule deleted");
      loadRules();
    } catch {
      message.error("Failed to delete rule");
    }
  };

  const handleEvaluate = async (values: Record<string, unknown>) => {
    setEvalLoading(true);
    try {
      const { data } = await axios.post("/api/rules/evaluate", null, {
        params: {
          camera_id: values.camera_id,
          defect_type: values.defect_type || undefined,
          anomaly_score: values.anomaly_score || undefined,
          classifier_prediction: values.classifier_prediction || undefined,
        },
      });
      setEvalResult(data);
    } catch {
      message.error("Evaluation failed");
    } finally {
      setEvalLoading(false);
    }
  };

  const handleGenerateFromKb = async (values: Record<string, unknown>) => {
    setSubmitting(true);
    try {
      const { data } = await axios.post(
        `/api/rules/generate-from-knowledge?knowledge_entry_id=${values.knowledge_entry_id}`
      );
      message.success(`Generated ${data.length} rule(s)`);
      setGenFromKbVisible(false);
      kbForm.resetFields();
      loadRules();
    } catch {
      message.error("Failed to generate rules");
    } finally {
      setSubmitting(false);
    }
  };

  const ruleTypeColorMap: Record<string, string> = {
    ignore: "green",
    flag: "orange",
    escalate: "red",
  };

  const columns = [
    {
      title: "Name",
      dataIndex: "name",
      key: "name",
      render: (n: string) => <Text strong>{n}</Text>,
    },
    {
      title: "Type",
      dataIndex: "rule_type",
      key: "rule_type",
      width: 90,
      render: (t: string) => (
        <Tag color={ruleTypeColorMap[t] || "default"}>{t.toUpperCase()}</Tag>
      ),
    },
    {
      title: "Priority",
      dataIndex: "priority",
      key: "priority",
      width: 70,
      sorter: (a: Rule, b: Rule) => a.priority - b.priority,
    },
    {
      title: "Enabled",
      dataIndex: "enabled",
      key: "enabled",
      width: 80,
      render: (enabled: boolean, record: Rule) => (
        <Switch
          checked={enabled}
          size="small"
          onChange={(checked) => handleToggle(record.rule_id, checked)}
        />
      ),
    },
    {
      title: "Description",
      dataIndex: "description",
      key: "description",
      ellipsis: true,
      render: (d: string | null) => (
        <Text type="secondary">{d || "-"}</Text>
      ),
    },
    {
      title: "Created",
      dataIndex: "created_at",
      key: "created_at",
      width: 170,
      render: (d: string) => new Date(d).toLocaleString(),
    },
    {
      title: "Actions",
      key: "actions",
      width: 100,
      render: (_: unknown, record: Rule) => (
        <Popconfirm
          title="Delete this rule?"
          onConfirm={() => handleDelete(record.rule_id)}
        >
          <Button type="link" size="small" danger icon={<DeleteOutlined />}>
            Delete
          </Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <h2>Rules Engine</h2>
        </Col>
        <Col>
          <Space>
            <Select
              placeholder="Rule Type"
              allowClear
              style={{ width: 130 }}
              value={typeFilter}
              onChange={setTypeFilter}
              options={[
                { value: "ignore", label: "Ignore" },
                { value: "flag", label: "Flag" },
                { value: "escalate", label: "Escalate" },
              ]}
            />
            <Button icon={<ReloadOutlined />} onClick={loadRules}>
              Refresh
            </Button>
            <Button
              icon={<BookOutlined />}
              onClick={() => setGenFromKbVisible(true)}
            >
              From KB
            </Button>
            <Button
              icon={<PlayCircleOutlined />}
              onClick={() => {
                setEvalResult(null);
                setEvalVisible(true);
              }}
            >
              Evaluate
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => {
                form.resetFields();
                setCreateVisible(true);
              }}
            >
              New Rule
            </Button>
          </Space>
        </Col>
      </Row>

      <Card>
        <Table
          columns={columns}
          dataSource={rules}
          rowKey="rule_id"
          loading={loading}
          pagination={{ pageSize: 20, showTotal: (t) => `Total ${t} rules` }}
          size="middle"
        />
      </Card>

      {/* Create Rule Modal */}
      <Modal
        title="Create Rule"
        open={createVisible}
        onCancel={() => {
          setCreateVisible(false);
          form.resetFields();
        }}
        onOk={() => form.submit()}
        confirmLoading={submitting}
        width={600}
      >
        <Form form={form} layout="vertical" onFinish={(v) => handleCreate(v)}>
          <Form.Item name="name" label="Name" rules={[{ required: true }]}>
            <Input placeholder="e.g. Ignore reflection on left camera" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="rule_type" label="Type" rules={[{ required: true }]}>
                <Select
                  options={[
                    { value: "ignore", label: "Ignore" },
                    { value: "flag", label: "Flag" },
                    { value: "escalate", label: "Escalate" },
                  ]}
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="priority" label="Priority" initialValue={0}>
                <InputNumber min={0} max={100} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item
            name="condition_json"
            label="Condition (JSON)"
            rules={[{ required: true }]}
            help='e.g. {"defect_type": "reflection", "min_score": 0.6}'
          >
            <TextArea
              rows={4}
              placeholder='{"defect_type": "reflection"}'
            />
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

      {/* Evaluate Rules Modal */}
      <Modal
        title="Evaluate Rules"
        open={evalVisible}
        onCancel={() => setEvalVisible(false)}
        footer={null}
        width={650}
      >
        <Form form={evalForm} layout="vertical" onFinish={(v) => handleEvaluate(v)}>
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
                  options={[
                    { value: "wrinkle", label: "Wrinkle" },
                    { value: "scratch", label: "Scratch" },
                    { value: "reflection", label: "Reflection" },
                    { value: "stain", label: "Stain" },
                    { value: "seam_shift", label: "Seam Shift" },
                  ]}
                />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="anomaly_score" label="Anomaly Score">
                <InputNumber min={0} max={1} step={0.01} style={{ width: "100%" }} placeholder="0.85" />
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
          <Button
            type="primary"
            htmlType="submit"
            loading={evalLoading}
            icon={<ThunderboltOutlined />}
          >
            Run Evaluation
          </Button>
        </Form>

        {evalResult && (
          <Card
            title="Evaluation Result"
            size="small"
            style={{ marginTop: 16 }}
          >
            <Descriptions column={2} size="small">
              <Descriptions.Item label="Final Action">
                <Tag
                  color={
                    evalResult.action === "ignore"
                      ? "green"
                      : evalResult.action === "escalate"
                      ? "red"
                      : "orange"
                  }
                  style={{ fontSize: 14, padding: "2px 12px" }}
                >
                  {evalResult.action.toUpperCase()}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Rules Matched">
                <Text strong>{evalResult.rule_count}</Text>
              </Descriptions.Item>
            </Descriptions>
            {evalResult.matched_rules.length > 0 && (
              <Table
                style={{ marginTop: 12 }}
                dataSource={evalResult.matched_rules}
                rowKey="rule_id"
                size="small"
                pagination={false}
                columns={[
                  { title: "Name", dataIndex: "name", key: "name" },
                  {
                    title: "Type",
                    dataIndex: "type",
                    key: "type",
                    render: (t: string) => (
                      <Tag color={ruleTypeColorMap[t] || "default"}>{t}</Tag>
                    ),
                  },
                  { title: "Priority", dataIndex: "priority", key: "priority" },
                ]}
              />
            )}
          </Card>
        )}
      </Modal>

      {/* Generate from Knowledge Modal */}
      <Modal
        title="Generate Rules from Knowledge Base"
        open={genFromKbVisible}
        onCancel={() => {
          setGenFromKbVisible(false);
          kbForm.resetFields();
        }}
        onOk={() => kbForm.submit()}
        confirmLoading={submitting}
      >
        <Form form={kbForm} layout="vertical" onFinish={(v) => handleGenerateFromKb(v)}>
          <Form.Item
            name="knowledge_entry_id"
            label="Knowledge Entry ID"
            rules={[{ required: true }]}
            help="Rules will be auto-generated based on the knowledge entry's category and action"
          >
            <Input placeholder="Enter knowledge entry ID" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
