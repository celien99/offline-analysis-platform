import { useState } from "react";
import {
  Card,
  Table,
  Button,
  Tag,
  Modal,
  Form,
  Input,
  Select,
  Space,
  message,
  Typography,
  Popconfirm,
} from "antd";
import {
  RocketOutlined,
  RollbackOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import PageHeader from "../../components/ui/PageHeader";
import { useDeployments, useDeployModel, useRollbackModel, useTrainedModels } from "../../hooks/queries";
import type { DeploymentRecord, TrainedModel } from "../../types";
import dayjs from "dayjs";

export default function ModelDeployPage() {
  const [page, setPage] = useState(1);
  const [deployVisible, setDeployVisible] = useState(false);
  const [deployForm] = Form.useForm();
  const [selectedModel, setSelectedModel] = useState<TrainedModel | null>(null);

  const { data: deployments, refetch: refetchDeployments } = useDeployments({ page });
  const { data: modelsData } = useTrainedModels({ page: 1 });
  const deployModel = useDeployModel();
  const rollbackModel = useRollbackModel();

  const handleDeploy = (values: Record<string, string>) => {
    deployModel.mutate(
      {
        model_name: values.model_name,
        version: values.version,
        target: values.target,
        deployed_by: values.deployed_by || undefined,
      },
      {
        onSuccess: () => {
          setDeployVisible(false);
          message.success("Model deployed");
          refetchDeployments();
        },
      },
    );
  };

  const handleRollback = (target: string) => {
    rollbackModel.mutate(
      { target, reason: "Manual rollback" },
      {
        onSuccess: () => {
          message.success(`Rollback for ${target} initiated`);
          refetchDeployments();
        },
      },
    );
  };

  const columns = [
    { title: "Deployment ID", dataIndex: "deployment_id", key: "deployment_id", width: 280, ellipsis: true },
    { title: "Model", dataIndex: "model_name", key: "model_name", width: 180 },
    { title: "Version", dataIndex: "version", key: "version", width: 140 },
    {
      title: "Target",
      dataIndex: "target",
      key: "target",
      width: 120,
      render: (t: string) => <Tag color="purple">{t}</Tag>,
    },
    {
      title: "Status",
      dataIndex: "deployment_status",
      key: "deployment_status",
      width: 100,
      render: (s: string) => (
        <Tag color={s === "active" ? "green" : s === "rolled_back" ? "orange" : "default"}>
          {s}
        </Tag>
      ),
    },
    {
      title: "Deployed At",
      dataIndex: "deployed_at",
      key: "deployed_at",
      width: 180,
      render: (d: string) => dayjs(d).format("YYYY-MM-DD HH:mm"),
    },
    {
      title: "Actions",
      key: "actions",
      width: 100,
      render: (_: unknown, record: DeploymentRecord) => (
        record.deployment_status === "active" ? (
          <Popconfirm
            title={`Rollback ${record.target}?`}
            onConfirm={() => handleRollback(record.target)}
          >
            <Button size="small" danger icon={<RollbackOutlined />}>
              Rollback
            </Button>
          </Popconfirm>
        ) : null
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Model Deployment"
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => refetchDeployments()}>
              Refresh
            </Button>
            <Button
              type="primary"
              icon={<RocketOutlined />}
              onClick={() => setDeployVisible(true)}
            >
              Deploy Model
            </Button>
          </Space>
        }
      />

      <Card>
        <Table
          columns={columns}
          dataSource={deployments ?? []}
          rowKey="deployment_id"
          loading={!deployments}
          pagination={{ current: page, onChange: (p) => setPage(p) }}
        />
      </Card>

      <Modal
        title="Deploy Model to Target"
        open={deployVisible}
        onCancel={() => setDeployVisible(false)}
        onOk={() => deployForm.submit()}
        confirmLoading={deployModel.isPending}
        width={500}
      >
        <Form
          form={deployForm}
          layout="vertical"
          onFinish={handleDeploy}
        >
          <Form.Item
            name="model_name"
            label="Model Name"
            rules={[{ required: true }]}
          >
            <Select
              showSearch
              placeholder="Select a trained model"
              options={(modelsData?.models ?? []).map((m) => ({
                value: m.model_name,
                label: `${m.model_name} (${m.version})`,
              }))}
              onChange={(_, opt) => {
                const model = modelsData?.models?.find(
                  (m) => m.model_name === (opt as { value: string })?.value,
                );
                if (model) {
                  deployForm.setFieldsValue({ version: model.version });
                  setSelectedModel(model);
                }
              }}
            />
          </Form.Item>
          <Form.Item name="version" label="Version" rules={[{ required: true }]}>
            <Input placeholder="e.g. 20250115120000" />
          </Form.Item>
          <Form.Item
            name="target"
            label="Deployment Target"
            rules={[{ required: true, message: "Target is required" }]}
          >
            <Select
              placeholder="e.g. production_line_1"
              options={[
                { value: "production_line_1", label: "Production Line 1" },
                { value: "production_line_2", label: "Production Line 2" },
                { value: "camera_group_a", label: "Camera Group A" },
                { value: "camera_group_b", label: "Camera Group B" },
              ]}
            />
          </Form.Item>
          <Form.Item name="deployed_by" label="Deployed By">
            <Input placeholder="Engineer name (optional)" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
