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
  Row,
  Col,
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
  useGateReport,
} from "../../hooks/queries";
import type { TrainingStartParams, TrainedModel } from "../../types";
import dayjs from "dayjs";
import TaskLogPanel from "./components/TaskLogPanel";

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
  const [gateModelId, setGateModelId] = useState<string | null>(null);
  const [gateModalVisible, setGateModalVisible] = useState(false);

  // PatchCore inline form state
  const [pcCameraId, setPcCameraId] = useState("");
  const [pcImageFiles, setPcImageFiles] = useState<File[]>([]);

  const [filterForm] = Form.useForm();

  const { data: modelsData, refetch: refetchModels } = useTrainedModels({ page });
  const filterStart = useTrainingStart();
  const patchcoreStart = usePatchCoreTrainingStart();
  const { data: statusData } = useTrainingStatus(statusTaskId);
  const { data: gateReport } = useGateReport(gateModelId);

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
          message.success("过滤器分类器训练已加入队列");
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
        message.success("PatchCore 训练已加入队列");
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
    { title: "模型名称", dataIndex: "model_name", key: "model_name" },
    { title: "版本", dataIndex: "version", key: "version", width: 140 },
    {
      title: "类型",
      dataIndex: "model_type",
      key: "model_type",
      width: 120,
      render: (t: string) => <Tag color={modelTypeColor(t)}>{t}</Tag>,
    },
    {
      title: "框架",
      dataIndex: "framework",
      key: "framework",
      width: 100,
      render: (f: string) => <Tag>{f}</Tag>,
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 110,
      render: (s: string) => {
        const colorMap: Record<string, string> = {
          registered: "blue",
          validated: "green",
          deployed: "purple",
          gate_failed: "red",
          retired: "default",
        };
        return <Tag color={colorMap[s] || "orange"}>{s}</Tag>;
      },
    },
    {
      title: "门禁",
      key: "gate",
      width: 80,
      render: (_: unknown, record: TrainedModel) => (
        <Button
          size="small"
          type="link"
          onClick={() => {
            setGateModelId(record.model_id);
            setGateModalVisible(true);
          }}
        >
          查看
        </Button>
      ),
    },
    {
      title: "训练时间",
      dataIndex: "trained_at",
      key: "trained_at",
      width: 180,
      render: (d: string | null) => (d ? dayjs(d).format("YYYY-MM-DD HH:mm") : "-"),
    },
    {
      title: "操作",
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
          状态
        </Button>
      ),
    },
  ];

  const tabItems = [
    {
      key: "models",
      label: "已训练模型",
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
      label: "过滤器分类器",
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
            开始过滤器分类器训练
          </Button>
        </Card>
      ),
    },
    {
      key: "patchcore",
      label: "PatchCore 训练",
      children: (
        <Card>
          <Typography.Paragraph type="secondary" className="mb-4">
            使用正常参考图像训练 PatchCore 异常检测模型。训练参数由内置配置文件控制，仅需提供目标相机 ID 和正常参考图像。
          </Typography.Paragraph>

          <Form layout="vertical" className="max-w-lg">
            <Form.Item label="相机ID" required>
              <Input
                placeholder="例如: cam_front"
                value={pcCameraId}
                onChange={(e) => setPcCameraId(e.target.value)}
              />
            </Form.Item>

            <Form.Item label="正常参考图像" required>
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
                开始 PatchCore 训练
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
        title="训练管理"
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => refetchModels()}>
              刷新
            </Button>
          </Space>
        }
      />

      <Row gutter={16}>
        <Col xs={24} xl={13}>
          <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />
        </Col>
        <Col xs={24} xl={11}>
          <TaskLogPanel />
        </Col>
      </Row>

      {/* ── Filter Classifier Modal ── */}
      <Modal
        title="开始过滤器分类器训练"
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
          <Form.Item name="model_type" label="模型架构">
            <Select options={FILTER_MODEL_TYPE_OPTIONS} />
          </Form.Item>
          <Space size="middle">
            <Form.Item name="num_classes" label="类别数">
              <InputNumber min={2} max={10} />
            </Form.Item>
            <Form.Item name="batch_size" label="批次大小">
              <InputNumber min={1} max={256} />
            </Form.Item>
            <Form.Item name="epochs" label="训练轮数">
              <InputNumber min={1} max={500} />
            </Form.Item>
          </Space>
          <Space size="middle">
            <Form.Item name="learning_rate" label="学习率">
              <InputNumber min={0.0001} max={0.1} step={0.0001} />
            </Form.Item>
            <Form.Item name="validation_split" label="验证集比例">
              <InputNumber min={0.1} max={0.5} step={0.05} />
            </Form.Item>
            <Form.Item name="augmentations" label="数据增强" valuePropName="checked">
              <Select options={[{ value: true, label: "是" }, { value: false, label: "否" }]} />
            </Form.Item>
          </Space>
        </Form>
      </Modal>

      {/* ── Status Modal ── */}
      <Modal
        title="训练状态"
        open={statusVisible}
        onCancel={() => setStatusVisible(false)}
        footer={null}
      >
        {statusData ? (
          <Descriptions column={1} size="small">
            <Descriptions.Item label="任务ID">{statusData.task_id}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={statusData.status === "success" ? "green" : "blue"}>
                {statusData.status}
              </Tag>
            </Descriptions.Item>
            {statusData.progress != null && (
              <Descriptions.Item label="进度">
                <Progress percent={Math.round(statusData.progress * 100)} />
              </Descriptions.Item>
            )}
            {statusData.metrics && (
              <Descriptions.Item label="指标">
                <pre className="text-xs">{JSON.stringify(statusData.metrics, null, 2)}</pre>
              </Descriptions.Item>
            )}
          </Descriptions>
        ) : (
          <Typography.Text type="secondary">加载状态中...</Typography.Text>
        )}
      </Modal>

      {/* ── Gate Report Modal ── */}
      <Modal
        title="上线门禁评估报告"
        open={gateModalVisible}
        onCancel={() => setGateModalVisible(false)}
        footer={null}
        width={640}
      >
        {gateReport ? (
          <Descriptions column={2} size="small" bordered>
            <Descriptions.Item label="门禁状态" span={2}>
              <Tag color={gateReport.status === "passed" ? "green" : gateReport.status === "failed" ? "red" : "orange"}>
                {gateReport.status === "passed" ? "通过" : gateReport.status === "failed" ? "未通过" : "评估中"}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="评估时间" span={2}>
              {dayjs(gateReport.evaluated_at).format("YYYY-MM-DD HH:mm:ss")}
            </Descriptions.Item>
            <Descriptions.Item label="总样本数">{gateReport.total_samples ?? "-"}</Descriptions.Item>
            <Descriptions.Item label="真实缺陷样本">{gateReport.real_defect_samples ?? "-"}</Descriptions.Item>
            <Descriptions.Item label="真实缺陷召回率">
              <strong>{gateReport.real_defect_recall != null ? (gateReport.real_defect_recall * 100).toFixed(1) + "%" : "-"}</strong>
            </Descriptions.Item>
            <Descriptions.Item label="基线召回率">
              {gateReport.baseline_real_defect_recall != null ? (gateReport.baseline_real_defect_recall * 100).toFixed(1) + "%" : "（无基线）"}
            </Descriptions.Item>
            <Descriptions.Item label="误报抑制率">
              <strong>{gateReport.false_alarm_suppression_rate != null ? (gateReport.false_alarm_suppression_rate * 100).toFixed(1) + "%" : "-"}</strong>
            </Descriptions.Item>
            <Descriptions.Item label="基线抑制率">
              {gateReport.baseline_false_alarm_suppression_rate != null ? (gateReport.baseline_false_alarm_suppression_rate * 100).toFixed(1) + "%" : "（无基线）"}
            </Descriptions.Item>
            <Descriptions.Item label="被抑制的真实缺陷">
              <span style={{ color: (gateReport.suppressed_real_defect_count ?? 0) > 0 ? "red" : "green" }}>
                {gateReport.suppressed_real_defect_count ?? 0}
              </span>
            </Descriptions.Item>
            <Descriptions.Item label="评估者">{gateReport.evaluated_by}</Descriptions.Item>
            {gateReport.failure_reasons && gateReport.failure_reasons.length > 0 && (
              <Descriptions.Item label="失败原因" span={2}>
                <ul className="m-0 pl-5">
                  {gateReport.failure_reasons.map((r, i) => (
                    <li key={i} className="text-red-500">{r}</li>
                  ))}
                </ul>
              </Descriptions.Item>
            )}
            {gateReport.metrics && (
              <Descriptions.Item label="完整指标" span={2}>
                <pre className="text-xs">{JSON.stringify(gateReport.metrics, null, 2)}</pre>
              </Descriptions.Item>
            )}
          </Descriptions>
        ) : (
          <Typography.Text type="secondary">加载中...</Typography.Text>
        )}
      </Modal>
    </div>
  );
}
