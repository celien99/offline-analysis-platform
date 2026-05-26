import { useState } from "react";
import {
  Card,
  Collapse,
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
import DeployTopology from "./components/DeployTopology";
import { useDeployments, useDeployModel, useDeployTargets, useRollbackModel, useTrainedModels, useHotReloadTargets } from "../../hooks/queries";
import type { DeploymentRecord, TrainedModel } from "../../types";
import type { HotReloadTarget } from "../../api/hot-reload";
import dayjs from "dayjs";

export default function ModelDeployPage() {
  const [page, setPage] = useState(1);
  const [deployVisible, setDeployVisible] = useState(false);
  const [deployForm] = Form.useForm();
  const [selectedModel, setSelectedModel] = useState<TrainedModel | null>(null);

  const { data: deployments, refetch: refetchDeployments } = useDeployments({ page });
  const { data: modelsData } = useTrainedModels({ page: 1 });
  const { data: deployTargets } = useDeployTargets();
  const { data: hotReloadData } = useHotReloadTargets();
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
          message.success("模型已部署");
          refetchDeployments();
        },
      },
    );
  };

  const handleRollback = (target: string) => {
    rollbackModel.mutate(
      { target, reason: "手动回滚" },
      {
        onSuccess: () => {
          message.success(`${target} 的回滚已启动`);
          refetchDeployments();
        },
      },
    );
  };

  const columns = [
    { title: "部署ID", dataIndex: "deployment_id", key: "deployment_id", width: 280, ellipsis: true },
    { title: "模型", dataIndex: "model_name", key: "model_name", width: 180 },
    { title: "版本", dataIndex: "version", key: "version", width: 140 },
    {
      title: "目标",
      dataIndex: "target",
      key: "target",
      width: 120,
      render: (t: string) => <Tag color="purple">{t}</Tag>,
    },
    {
      title: "状态",
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
      title: "部署时间",
      dataIndex: "deployed_at",
      key: "deployed_at",
      width: 180,
      render: (d: string) => dayjs(d).format("YYYY-MM-DD HH:mm"),
    },
    {
      title: "操作",
      key: "actions",
      width: 100,
      render: (_: unknown, record: DeploymentRecord) => (
        record.deployment_status === "active" ? (
          <Popconfirm
            title={`确定要回滚 ${record.target} 吗？`}
            onConfirm={() => handleRollback(record.target)}
          >
            <Button size="small" danger icon={<RollbackOutlined />}>
              回滚
            </Button>
          </Popconfirm>
        ) : null
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="模型部署"
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => refetchDeployments()}>
              刷新
            </Button>
            <Button
              type="primary"
              icon={<RocketOutlined />}
              onClick={() => setDeployVisible(true)}
            >
              部署模型
            </Button>
          </Space>
        }
      />

      {/* ── Deployment Topology ── */}
      <DeployTopology
        targets={hotReloadData?.targets?.map((t: HotReloadTarget) => ({
          target: String(t.target ?? ""),
          activeModel: String(t.active_model ?? ""),
          activeVersion: String(t.active_version ?? ""),
          hasShadow: Boolean(t.has_shadow),
        }))}
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

      {/* ── Hot Reload Status ── */}
      {hotReloadData?.targets && hotReloadData.targets.length > 0 && (
        <Collapse
          size="small"
          ghost
          defaultActiveKey={["hot-reload"]}
          items={[
            {
              key: "hot-reload",
              label: "热重载状态",
              children: (
        <Card>
          <Table
            dataSource={hotReloadData.targets as unknown as Record<string, unknown>[]}
            rowKey="target"
            pagination={false}
            size="small"
            columns={[
              { title: "目标", key: "target", render: (_: unknown, r: Record<string, unknown>) => <Tag color="purple">{String(r.target ?? "")}</Tag> },
              { title: "生产模型", key: "active_model", render: (_: unknown, r: Record<string, unknown>) => String(r.active_model ?? "-") },
              { title: "版本", key: "active_version", render: (_: unknown, r: Record<string, unknown>) => String(r.active_version ?? "-") },
              {
                title: "Checksum", key: "active_checksum",
                render: (_: unknown, r: Record<string, unknown>) => r.active_checksum ? <Typography.Text code>{String(r.active_checksum)}</Typography.Text> : "-",
              },
              {
                title: "完整性", key: "checksum_verified",
                render: (_: unknown, r: Record<string, unknown>) => (
                  <Tag color={r.checksum_verified ? "green" : "red"}>
                    {r.checksum_verified ? "通过" : "异常"}
                  </Tag>
                ),
              },
              {
                title: "热重载信号", key: "has_pending_reload",
                render: (_: unknown, r: Record<string, unknown>) => (
                  <Tag color={r.has_pending_reload ? "orange" : "default"}>
                    {r.has_pending_reload ? "待重载" : "已同步"}
                  </Tag>
                ),
              },
              {
                title: "影子模型", key: "has_shadow",
                render: (_: unknown, r: Record<string, unknown>) => (
                  r.has_shadow ? <Tag color="blue">有</Tag> : <span>-</span>
                ),
              },
              {
                title: "可回滚版本", key: "rollback_version",
                render: (_: unknown, r: Record<string, unknown>) => String(r.rollback_version ?? "-"),
              },
            ]}
          />
        </Card>
              ),
            },
          ]}
        >
        </Collapse>
      )}

      <Modal
        title="部署模型到目标"
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
            label="模型名称"
            rules={[{ required: true }]}
          >
            <Select
              showSearch
              placeholder="选择已训练模型"
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
          <Form.Item name="version" label="版本" rules={[{ required: true }]}>
            <Input placeholder="例如: 20250115120000" />
          </Form.Item>
          <Form.Item
            name="target"
            label="部署目标"
            rules={[{ required: true, message: "部署目标为必填项" }]}
          >
            <Select
              placeholder="选择部署目标"
              options={Object.entries(deployTargets ?? {}).map(([key, path]) => ({
                value: key,
                label: `${key} (${path})`,
              }))}
              loading={!deployTargets}
            />
          </Form.Item>
          <Form.Item name="deployed_by" label="部署人">
            <Input placeholder="工程师姓名 (可选)" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
