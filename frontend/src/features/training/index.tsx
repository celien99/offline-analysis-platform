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
  Tabs,
  Input,
  Upload,
} from "antd";
import {
  PlayCircleOutlined,
  ReloadOutlined,
  InboxOutlined,
} from "@ant-design/icons";

const { Dragger } = Upload;
import PageHeader from "../../components/ui/PageHeader";
import {
  useTrainingStart,
  useTrainedModels,
  useTrainingStatus,
  usePatchCoreTrainingStart,
} from "../../hooks/queries";
import type { TrainingStartParams, TrainedModel } from "../../types";
import dayjs from "dayjs";

const FILTER_MODEL_TYPE_OPTIONS = [
  { value: "mobilenet_v3_small", label: "MobileNetV3-Small" },
  { value: "efficientnet_b0", label: "EfficientNet-B0" },
  { value: "resnet18", label: "ResNet18" },
];

export default function TrainingPage() {
  const [page, setPage] = useState(1);
  const [filterVisible, setFilterVisible] = useState(false);
  const [statusVisible, setStatusVisible] = useState(false);
  const [statusTaskId, setStatusTaskId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("models");

  // PatchCore inline form state
  const [pcCameraId, setPcCameraId] = useState("");
  const [pcImageFiles, setPcImageFiles] = useState<File[]>([]);

  const [filterForm] = Form.useForm();

  const { data: modelsData, refetch: refetchModels } = useTrainedModels({ page });
  const filterStart = useTrainingStart();
  const patchcoreStart = usePatchCoreTrainingStart();
  const { data: statusData } = useTrainingStatus(statusTaskId);

  // ── Filter Classifier ──
  const handleFilterStart = (values: TrainingStartParams) => {
    filterStart.mutate(
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
          setFilterVisible(false);
          message.success("Filter Classifier training queued");
          refetchModels();
        },
      },
    );
  };

  // ── PatchCore ──
  const handlePatchcoreStart = () => {
    if (!pcCameraId.trim()) {
      message.error("请输入 Camera ID");
      return;
    }
    if (pcImageFiles.length === 0) {
      message.error("请上传正常参考图像");
      return;
    }

    const formData = new FormData();
    formData.append("camera_id", pcCameraId.trim());
    pcImageFiles.forEach((f) => formData.append("good_images", f));

    patchcoreStart.mutate(formData, {
      onSuccess: () => {
        message.success("PatchCore training queued");
        setPcImageFiles([]);
        refetchModels();
      },
    });
  };

  const modelTypeColor = (t: string) => {
    if (t === "patchcore") return "purple";
    return "green";
  };

  const columns = [
    { title: "Model Name", dataIndex: "model_name", key: "model_name" },
    { title: "Version", dataIndex: "version", key: "version", width: 140 },
    {
      title: "Type",
      dataIndex: "model_type",
      key: "model_type",
      width: 120,
      render: (t: string) => <Tag color={modelTypeColor(t)}>{t}</Tag>,
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
      width: 100,
      render: (_: unknown, record: TrainedModel) => (
        <Button
          size="small"
          onClick={() => {
            setStatusTaskId(record.model_id);
            setStatusVisible(true);
          }}
        >
          Status
        </Button>
      ),
    },
  ];

  const tabItems = [
    {
      key: "models",
      label: "Trained Models",
      children: (
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
      ),
    },
    {
      key: "filter",
      label: "Filter Classifier",
      children: (
        <Card>
          <Typography.Paragraph type="secondary">
            从已审核的聚类数据中训练二分类过滤器，用于在线检测中抑制 PatchCore 误报。
          </Typography.Paragraph>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            onClick={() => setFilterVisible(true)}
          >
            Start Filter Classifier Training
          </Button>
        </Card>
      ),
    },
    {
      key: "patchcore",
      label: "PatchCore Training",
      children: (
        <Card>
          <Typography.Paragraph type="secondary" className="mb-4">
            使用正常参考图像训练 PatchCore 异常检测模型。训练参数由内置配置文件控制，仅需提供目标相机 ID 和正常参考图像。
          </Typography.Paragraph>

          <Form layout="vertical" className="max-w-lg">
            <Form.Item label="Camera ID" required>
              <Input
                placeholder="例如: cam_front"
                value={pcCameraId}
                onChange={(e) => setPcCameraId(e.target.value)}
              />
            </Form.Item>

            <Form.Item label="Good Reference Images" required>
              <Dragger
                multiple
                accept="image/*"
                beforeUpload={(file) => {
                  setPcImageFiles((prev) => [...prev, file]);
                  return false;
                }}
                onRemove={(file) => {
                  setPcImageFiles((prev) => prev.filter((f) => f.name !== file.name || f.size !== file.size));
                }}
                fileList={pcImageFiles.map((f, i) => ({ uid: `pc-${i}`, name: f.name, status: "done" as const, originFileObj: f })) as any}
              >
                <p className="ant-upload-drag-icon">
                  <InboxOutlined />
                </p>
                <p className="ant-upload-text">点击或拖拽图像文件到此处上传</p>
                <p className="ant-upload-hint">支持批量上传，每张图片作为正常参考样本</p>
              </Dragger>
            </Form.Item>

            <Form.Item>
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                size="large"
                onClick={handlePatchcoreStart}
                loading={patchcoreStart.isPending}
              >
                Start PatchCore Training
              </Button>
            </Form.Item>
          </Form>
        </Card>
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
          </Space>
        }
      />

      <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />

      {/* ── Filter Classifier Modal ── */}
      <Modal
        title="Start Filter Classifier Training"
        open={filterVisible}
        onCancel={() => setFilterVisible(false)}
        onOk={() => filterForm.submit()}
        confirmLoading={filterStart.isPending}
        width={600}
      >
        <Form
          form={filterForm}
          layout="vertical"
          onFinish={handleFilterStart}
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
            <Select options={FILTER_MODEL_TYPE_OPTIONS} />
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

      {/* ── Status Modal ── */}
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
