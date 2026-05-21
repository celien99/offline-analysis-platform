import { useState } from "react";
import {
  Card,
  Table,
  Button,
  Tag,
  Modal,
  InputNumber,
  Select,
  Form,
  Space,
  message,
  Typography,
  Progress,
  Descriptions,
} from "antd";
import {
  PlayCircleOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import PageHeader from "../../components/ui/PageHeader";
import {
  useTrainingStart,
  useTrainedModels,
  useTrainingStatus,
} from "../../hooks/queries";
import type { TrainingStartParams, TrainedModel } from "../../types";
import dayjs from "dayjs";

const MODEL_TYPE_OPTIONS = [
  { value: "mobilenet_v3_small", label: "MobileNetV3-Small" },
  { value: "efficientnet_lite", label: "EfficientNet-B0" },
  { value: "resnet18", label: "ResNet18" },
];

export default function TrainingPage() {
  const [page, setPage] = useState(1);
  const [trainVisible, setTrainVisible] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [trainForm] = Form.useForm();
  const [statusVisible, setStatusVisible] = useState(false);
  const [statusTaskId, setStatusTaskId] = useState<string | null>(null);

  const { data: modelsData, refetch: refetchModels } = useTrainedModels({ page });
  const trainingStart = useTrainingStart();
  const { data: statusData } = useTrainingStatus(taskId);

  const handleStartTraining = (values: TrainingStartParams) => {
    trainingStart.mutate(
      {
        model_type: values.model_type ?? "mobilenet_v3_small",
        num_classes: values.num_classes ?? 2,
        batch_size: values.batch_size ?? 32,
        epochs: values.epochs ?? 50,
        learning_rate: values.learning_rate ?? 0.001,
        validation_split: values.validation_split ?? 0.2,
        augmentations: values.augmentations ?? true,
      },
      {
        onSuccess: () => {
          setTrainVisible(false);
          message.success("Training queued");
          refetchModels();
        },
      },
    );
  };

  const columns = [
    { title: "Model Name", dataIndex: "model_name", key: "model_name" },
    { title: "Version", dataIndex: "version", key: "version", width: 140 },
    {
      title: "Type",
      dataIndex: "model_type",
      key: "model_type",
      width: 140,
      render: (t: string) => <Tag color="blue">{t}</Tag>,
    },
    {
      title: "Framework",
      dataIndex: "framework",
      key: "framework",
      width: 100,
      render: (f: string) => <Tag>{f}</Tag>,
    },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      width: 100,
      render: (s: string) => (
        <Tag color={s === "registered" ? "green" : "orange"}>{s}</Tag>
      ),
    },
    {
      title: "Trained At",
      dataIndex: "trained_at",
      key: "trained_at",
      width: 180,
      render: (d: string | null) => (d ? dayjs(d).format("YYYY-MM-DD HH:mm") : "-"),
    },
    {
      title: "Actions",
      key: "actions",
      width: 120,
      render: (_: unknown, record: TrainedModel) => (
        <Space>
          <Button
            size="small"
            onClick={() => {
              setStatusTaskId(record.model_id);
              setStatusVisible(true);
            }}
          >
            Status
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Training Management"
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => refetchModels()}>
              Refresh
            </Button>
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={() => setTrainVisible(true)}
            >
              Start New Training
            </Button>
          </Space>
        }
      />

      <Card>
        <Table
          columns={columns}
          dataSource={modelsData?.models ?? []}
          rowKey="model_id"
          loading={!modelsData}
          pagination={{
            current: page,
            total: modelsData?.total ?? 0,
            onChange: (p) => setPage(p),
          }}
        />
      </Card>

      <Modal
        title="Start New Training"
        open={trainVisible}
        onCancel={() => setTrainVisible(false)}
        onOk={() => trainForm.submit()}
        confirmLoading={trainingStart.isPending}
        width={600}
      >
        <Form
          form={trainForm}
          layout="vertical"
          onFinish={handleStartTraining}
          initialValues={{
            model_type: "mobilenet_v3_small",
            num_classes: 2,
            batch_size: 32,
            epochs: 50,
            learning_rate: 0.001,
            validation_split: 0.2,
            augmentations: true,
          }}
        >
          <Form.Item name="model_type" label="Model Architecture">
            <Select options={MODEL_TYPE_OPTIONS} />
          </Form.Item>
          <Space size="middle">
            <Form.Item name="num_classes" label="Num Classes">
              <InputNumber min={2} max={10} />
            </Form.Item>
            <Form.Item name="batch_size" label="Batch Size">
              <InputNumber min={1} max={256} />
            </Form.Item>
            <Form.Item name="epochs" label="Epochs">
              <InputNumber min={1} max={500} />
            </Form.Item>
          </Space>
          <Space size="middle">
            <Form.Item name="learning_rate" label="Learning Rate">
              <InputNumber min={0.0001} max={0.1} step={0.0001} />
            </Form.Item>
            <Form.Item name="validation_split" label="Validation Split">
              <InputNumber min={0.1} max={0.5} step={0.05} />
            </Form.Item>
            <Form.Item name="augmentations" label="Augmentations" valuePropName="checked">
              <Select options={[{ value: true, label: "Yes" }, { value: false, label: "No" }]} />
            </Form.Item>
          </Space>
        </Form>
      </Modal>

      <Modal
        title="Training Status"
        open={statusVisible}
        onCancel={() => setStatusVisible(false)}
        footer={null}
      >
        {statusData ? (
          <Descriptions column={1} size="small">
            <Descriptions.Item label="Task ID">{statusData.task_id}</Descriptions.Item>
            <Descriptions.Item label="Status">
              <Tag color={statusData.status === "success" ? "green" : "blue"}>
                {statusData.status}
              </Tag>
            </Descriptions.Item>
            {statusData.progress != null && (
              <Descriptions.Item label="Progress">
                <Progress percent={Math.round(statusData.progress * 100)} />
              </Descriptions.Item>
            )}
            {statusData.metrics && (
              <Descriptions.Item label="Metrics">
                <pre className="text-xs">{JSON.stringify(statusData.metrics, null, 2)}</pre>
              </Descriptions.Item>
            )}
          </Descriptions>
        ) : (
          <Typography.Text type="secondary">Loading status...</Typography.Text>
        )}
      </Modal>
    </div>
  );
}
