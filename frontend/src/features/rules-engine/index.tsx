import { useEffect, useState } from "react";
import { Card, Table, Button, Space, Select, message, Form } from "antd";
import { PlusOutlined, ReloadOutlined, PlayCircleOutlined, BookOutlined } from "@ant-design/icons";
import { Modal, Input } from "antd";
import type { Rule, EvalResult } from "../../types";
import { rulesApi } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import { useRulesColumns } from "./components/RulesTable";
import CreateRuleForm from "./components/CreateRuleForm";
import EvaluateRuleForm from "./components/EvaluateRuleForm";
import EvalResultDisplay from "./components/EvalResult";
import { RULE_TYPE_OPTIONS } from "../../lib/constants";

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

  const load = async () => {
    setLoading(true);
    try {
      setRules(await rulesApi.list({ rule_type: typeFilter, page_size: 200 }));
    } catch {
      message.error("Failed to load rules");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
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
      await rulesApi.create({
        name: values.name,
        rule_type: values.rule_type,
        condition_json: conditionJson,
        priority: values.priority,
        description: values.description,
        camera_ids: values.camera_ids || undefined,
        knowledge_entry_id: values.knowledge_entry_id || undefined,
      });
      message.success("Rule created");
      setCreateVisible(false);
      form.resetFields();
      load();
    } catch {
      message.error("Failed to create rule");
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggle = async (ruleId: string, enabled: boolean) => {
    try {
      await rulesApi.toggle(ruleId, enabled);
      message.success(`Rule ${enabled ? "enabled" : "disabled"}`);
      load();
    } catch {
      message.error("Failed to toggle rule");
    }
  };

  const handleDelete = async (ruleId: string) => {
    try {
      await rulesApi.delete(ruleId);
      message.success("Rule deleted");
      load();
    } catch {
      message.error("Failed to delete rule");
    }
  };

  const handleEvaluate = async (values: Record<string, unknown>) => {
    setEvalLoading(true);
    try {
      setEvalResult(
        await rulesApi.evaluate({
          camera_id: values.camera_id as string,
          defect_type: values.defect_type as string | undefined,
          anomaly_score: values.anomaly_score as number | undefined,
          classifier_prediction: values.classifier_prediction as string | undefined,
        }),
      );
    } catch {
      message.error("Evaluation failed");
    } finally {
      setEvalLoading(false);
    }
  };

  const handleGenerateFromKb = async (values: Record<string, unknown>) => {
    setSubmitting(true);
    try {
      const data = await rulesApi.generateFromKnowledge(values.knowledge_entry_id as string);
      message.success(`Generated ${(data as unknown[]).length} rule(s)`);
      setGenFromKbVisible(false);
      kbForm.resetFields();
      load();
    } catch {
      message.error("Failed to generate rules");
    } finally {
      setSubmitting(false);
    }
  };

  const columns = useRulesColumns({ onToggle: handleToggle, onDelete: handleDelete });

  return (
    <div>
      <PageHeader
        title="Rules Engine"
        extra={
          <Space>
            <Select
              placeholder="Rule Type"
              allowClear
              style={{ width: 130 }}
              value={typeFilter}
              onChange={setTypeFilter}
              options={RULE_TYPE_OPTIONS as { value: string; label: string }[]}
            />
            <Button icon={<ReloadOutlined />} onClick={load}>Refresh</Button>
            <Button icon={<BookOutlined />} onClick={() => setGenFromKbVisible(true)}>From KB</Button>
            <Button
              icon={<PlayCircleOutlined />}
              onClick={() => { setEvalResult(null); setEvalVisible(true); }}
            >
              Evaluate
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => { form.resetFields(); setCreateVisible(true); }}
            >
              New Rule
            </Button>
          </Space>
        }
      />

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

      <CreateRuleForm
        form={form}
        open={createVisible}
        submitting={submitting}
        onSubmit={handleCreate}
        onClose={() => { setCreateVisible(false); form.resetFields(); }}
      />

      <EvaluateRuleForm
        form={evalForm}
        open={evalVisible}
        loading={evalLoading}
        onSubmit={handleEvaluate}
        onClose={() => setEvalVisible(false)}
      />

      {evalResult && <EvalResultDisplay result={evalResult} />}

      <Modal
        title="Generate Rules from Knowledge Base"
        open={genFromKbVisible}
        onCancel={() => { setGenFromKbVisible(false); kbForm.resetFields(); }}
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
