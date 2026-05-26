import { useState } from "react";
import { Card, Table, Button, Space, Select, message, Form } from "antd";
import { PlusOutlined, ReloadOutlined, PlayCircleOutlined, BookOutlined, CloudUploadOutlined } from "@ant-design/icons";
import { Modal, Input } from "antd";
import type { EvalResult } from "../../types";
import { useRulesList, useRuleCreate, useRuleToggle, useRuleDelete, useRuleEvaluate, useRuleGenerateFromKb, useRuleDeploy } from "../../hooks/queries";
import PageHeader from "../../components/ui/PageHeader";
import { useRulesColumns } from "./components/RulesTable";
import CreateRuleForm from "./components/CreateRuleForm";
import EvaluateRuleForm from "./components/EvaluateRuleForm";
import EvalResultDisplay from "./components/EvalResult";
import { RULE_TYPE_OPTIONS } from "../../lib/constants";

export default function RulesManagement() {
  const [typeFilter, setTypeFilter] = useState<string | undefined>();
  const [createVisible, setCreateVisible] = useState(false);
  const [evalVisible, setEvalVisible] = useState(false);
  const [evalResult, setEvalResult] = useState<EvalResult | null>(null);
  const [genFromKbVisible, setGenFromKbVisible] = useState(false);
  const [form] = Form.useForm();
  const [evalForm] = Form.useForm();
  const [kbForm] = Form.useForm();

  const { data: rules = [], isLoading, refetch } = useRulesList(typeFilter);
  const createMutation = useRuleCreate();
  const toggleMutation = useRuleToggle();
  const deleteMutation = useRuleDelete();
  const evaluateMutation = useRuleEvaluate();
  const generateMutation = useRuleGenerateFromKb();
  const deployMutation = useRuleDeploy();

  const handleDeploy = async () => {
    try {
      const data = await deployMutation.mutateAsync("production_line_a");
      message.success(`已部署 ${data.rule_count} 条规则到 ${data.target}`);
    } catch {
      message.error("规则部署失败");
    }
  };

  const handleCreate = async (values: Record<string, unknown>) => {
    try {
      let conditionJson = "{}";
      try {
        JSON.parse(values.condition_json as string);
        conditionJson = values.condition_json as string;
      } catch {
        message.error("条件中的 JSON 格式无效");
        return;
      }
      await createMutation.mutateAsync({
        name: values.name,
        rule_type: values.rule_type,
        condition_json: conditionJson,
        priority: values.priority,
        description: values.description,
        camera_ids: values.camera_ids || undefined,
        knowledge_entry_id: values.knowledge_entry_id || undefined,
      });
      message.success("规则已创建");
      setCreateVisible(false);
      form.resetFields();
    } catch {
      message.error("创建规则失败");
    }
  };

  const handleToggle = async (ruleId: string, enabled: boolean) => {
    try {
      await toggleMutation.mutateAsync({ ruleId, enabled });
      message.success(`规则已${enabled ? "启用" : "禁用"}`);
    } catch {
      message.error("切换规则状态失败");
    }
  };

  const handleDelete = async (ruleId: string) => {
    try {
      await deleteMutation.mutateAsync(ruleId);
      message.success("规则已删除");
    } catch {
      message.error("删除规则失败");
    }
  };

  const handleEvaluate = async (values: Record<string, unknown>) => {
    try {
      setEvalResult(
        await evaluateMutation.mutateAsync({
          camera_id: values.camera_id as string,
          defect_type: values.defect_type as string | undefined,
          anomaly_score: values.anomaly_score as number | undefined,
          classifier_prediction: values.classifier_prediction as string | undefined,
        }),
      );
    } catch {
      message.error("评估失败");
    }
  };

  const handleGenerateFromKb = async (values: Record<string, unknown>) => {
    try {
      const data = await generateMutation.mutateAsync(values.knowledge_entry_id as string);
      message.success(`已生成 ${data.length} 条规则`);
      setGenFromKbVisible(false);
      kbForm.resetFields();
    } catch {
      message.error("生成规则失败");
    }
  };

  const columns = useRulesColumns({ onToggle: handleToggle, onDelete: handleDelete });

  return (
    <div>
      <PageHeader
        title="规则引擎"
        extra={
          <Space>
            <Select
              placeholder="规则类型"
              allowClear
              className="w-[130px]"
              value={typeFilter}
              onChange={setTypeFilter}
              options={RULE_TYPE_OPTIONS as { value: string; label: string }[]}
            />
            <Button icon={<ReloadOutlined />} onClick={() => refetch()}>刷新</Button>
            <Button icon={<CloudUploadOutlined />} loading={deployMutation.isPending} onClick={handleDeploy}>部署规则</Button>
            <Button icon={<BookOutlined />} onClick={() => setGenFromKbVisible(true)}>从知识库</Button>
            <Button
              icon={<PlayCircleOutlined />}
              onClick={() => { setEvalResult(null); setEvalVisible(true); }}
            >
              评估
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => { form.resetFields(); setCreateVisible(true); }}
            >
              新建规则
            </Button>
          </Space>
        }
      />

      <Card>
        <Table
          columns={columns}
          dataSource={rules}
          rowKey="rule_id"
          loading={isLoading}
          pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 条规则` }}
          size="middle"
        />
      </Card>

      <CreateRuleForm
        form={form}
        open={createVisible}
        submitting={createMutation.isPending}
        onSubmit={handleCreate}
        onClose={() => { setCreateVisible(false); form.resetFields(); }}
      />

      <EvaluateRuleForm
        form={evalForm}
        open={evalVisible}
        loading={evaluateMutation.isPending}
        onSubmit={handleEvaluate}
        onClose={() => setEvalVisible(false)}
      />

      {evalResult && <EvalResultDisplay result={evalResult} />}

      <Modal
        title="从知识库生成规则"
        open={genFromKbVisible}
        onCancel={() => { setGenFromKbVisible(false); kbForm.resetFields(); }}
        onOk={() => kbForm.submit()}
        confirmLoading={generateMutation.isPending}
      >
        <Form form={kbForm} layout="vertical" onFinish={(v) => handleGenerateFromKb(v)}>
          <Form.Item
            name="knowledge_entry_id"
            label="知识条目ID"
            rules={[{ required: true }]}
            help="规则将根据知识条目的类别和动作自动生成"
          >
            <Input placeholder="输入知识条目ID" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
