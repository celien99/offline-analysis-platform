import { useState } from "react";
import {
  Card,
  Table,
  Button,
  Tag,
  Input,
  Upload,
  Space,
  message,
  Typography,
  Descriptions,
  Row,
  Col,
  Progress,
  Spin,
} from "antd";
import {
  PlayCircleOutlined,
  PlusOutlined,
  DeleteOutlined,
  InboxOutlined,
  ScanOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import PageHeader from "../../components/ui/PageHeader";
import { useInspectionRun, useInspectionResult } from "../../hooks/queries";

const { Dragger } = Upload;

interface CameraSlot {
  key: number;
  cameraId: string;
  file: File | null;
}

const DEFAULT_CAMERAS = [
  { key: 0, cameraId: "cam_front", file: null },
  { key: 1, cameraId: "cam_side", file: null },
];

export default function InspectionPage() {
  const [slots, setSlots] = useState<CameraSlot[]>(DEFAULT_CAMERAS);
  const [nextKey, setNextKey] = useState(DEFAULT_CAMERAS.length);
  const [taskId, setTaskId] = useState<string | null>(null);

  const runMutation = useInspectionRun();
  const { data: result, isFetching } = useInspectionResult(taskId);

  const addSlot = () => {
    setSlots([...slots, { key: nextKey, cameraId: "", file: null }]);
    setNextKey(nextKey + 1);
  };

  const removeSlot = (key: number) => {
    if (slots.length <= 1) return;
    setSlots(slots.filter((s) => s.key !== key));
  };

  const updateSlot = (key: number, patch: Partial<CameraSlot>) => {
    setSlots(slots.map((s) => (s.key === key ? { ...s, ...patch } : s)));
  };

  const handleRun = () => {
    const filled = slots.filter((s) => s.cameraId.trim() && s.file);
    if (filled.length === 0) {
      message.error("请至少配置一个相机并上传图像");
      return;
    }

    const formData = new FormData();
    formData.append("camera_ids", filled.map((s) => s.cameraId.trim()).join(","));
    filled.forEach((s) => formData.append("image_files", s.file!));

    runMutation.mutate(formData, {
      onSuccess: (data) => {
        message.success("检测任务已提交");
        setTaskId(data.task_id ?? null);
      },
      onError: () => message.error("检测任务提交失败"),
    });
  };

  const handleReset = () => {
    setTaskId(null);
    setSlots(DEFAULT_CAMERAS.map((s) => ({ ...s, file: null })));
  };

  const statusColor = (s: string) => {
    if (s === "OK" || s === "SUCCESS") return "green";
    if (s === "NG") return "red";
    if (s === "REJECT") return "orange";
    if (s === "FAILURE" || s === "FAILED") return "red";
    if (s === "PENDING" || s === "STARTED") return "blue";
    return "default";
  };

  const isRunning = !!taskId && (!result || result.status === "PENDING" || result.status === "STARTED");

  return (
    <div>
      <PageHeader
        title="Inspection"
        extra={
          <Button icon={<ReloadOutlined />} onClick={handleReset} disabled={isRunning}>
            Reset
          </Button>
        }
      />

      <Row gutter={24}>
        {/* 左侧：相机上传区 */}
        <Col span={10}>
          <Card
            title={
              <Space>
                <ScanOutlined />
                Camera Images
              </Space>
            }
            extra={
              <Button icon={<PlusOutlined />} onClick={addSlot} disabled={isRunning} size="small">
                Add Camera
              </Button>
            }
          >
            <Typography.Paragraph type="secondary" className="text-xs mb-2">
              为每个相机填写 ID 并拖拽上传对应图像。
            </Typography.Paragraph>

            {slots.map((slot) => (
              <div key={slot.key} className="mb-3 p-3 border rounded-lg border-gray-200">
                <Row gutter={8} align="middle" className="mb-2">
                  <Col flex="auto">
                    <Input
                      placeholder="Camera ID"
                      value={slot.cameraId}
                      onChange={(e) => updateSlot(slot.key, { cameraId: e.target.value })}
                      disabled={isRunning}
                      size="small"
                    />
                  </Col>
                  <Col>
                    <Button
                      icon={<DeleteOutlined />}
                      danger
                      size="small"
                      onClick={() => removeSlot(slot.key)}
                      disabled={slots.length <= 1 || isRunning}
                    />
                  </Col>
                </Row>
                <Dragger
                  accept="image/*"
                  maxCount={1}
                  disabled={isRunning}
                  beforeUpload={(file) => {
                    updateSlot(slot.key, { file });
                    return false;
                  }}
                  onRemove={() => updateSlot(slot.key, { file: null })}
                  className={slot.file ? "border-green-400" : ""}
                >
                  <p className="ant-upload-drag-icon">
                    <InboxOutlined />
                  </p>
                  <p className="ant-upload-text">
                    {slot.file ? slot.file.name : "点击或拖拽图像到此区域"}
                  </p>
                </Dragger>
              </div>
            ))}

            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              size="large"
              block
              onClick={handleRun}
              loading={runMutation.isPending}
              disabled={isRunning}
            >
              Run Inspection
            </Button>
          </Card>
        </Col>

        {/* 右侧：检测结果 */}
        <Col span={14}>
          <Card title="Inspection Result">
            {isRunning && (
              <div className="text-center py-8">
                <Spin size="large" tip="检测运行中，请稍候..." />
              </div>
            )}

            {result && !isRunning && (
              <>
                <Descriptions column={2} size="small" bordered className="mb-4">
                  <Descriptions.Item label="Task ID" span={2}>
                    {result.task_id}
                  </Descriptions.Item>
                  <Descriptions.Item label="Task Status">
                    <Tag color={statusColor(result.status)}>{result.status}</Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="Overall">
                    <Tag color={statusColor(result.overall_status ?? "")}>
                      {result.overall_status ?? "-"}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="Decision Reason" span={2}>
                    {result.decision_reason ?? "-"}
                  </Descriptions.Item>
                </Descriptions>

                {result.error_message && (
                  <Typography.Text type="danger" className="block mb-4">
                    {result.error_message}
                  </Typography.Text>
                )}

                {result.camera_results.length > 0 && (
                  <>
                    <Typography.Title level={5}>Per-Camera Results</Typography.Title>
                    <Table
                      columns={[
                        { title: "Camera ID", dataIndex: "camera_id", width: 120 },
                        {
                          title: "Status",
                          dataIndex: "status",
                          width: 90,
                          render: (s: string) => <Tag color={statusColor(s)}>{s}</Tag>,
                        },
                        {
                          title: "Anomaly Score",
                          dataIndex: "anomaly_score",
                          width: 120,
                          render: (v: number | null) => (
                            v != null ? (
                              <Space size={4}>
                                <span className="text-xs">{v.toFixed(4)}</span>
                                <Progress
                                  percent={Math.min(v * 100, 100)}
                                  showInfo={false}
                                  size="small"
                                  strokeColor={v > 0.5 ? "#ff4d4f" : "#52c41a"}
                                  className="w-12 inline-block"
                                />
                              </Space>
                            ) : "-"
                          ),
                        },
                        {
                          title: "Is Anomaly",
                          dataIndex: "is_anomaly",
                          width: 90,
                          render: (v: boolean | null) => (v == null ? "-" : <Tag color={v ? "red" : "green"}>{v ? "Yes" : "No"}</Tag>),
                        },
                        { title: "Reason", dataIndex: "decision_reason", ellipsis: true },
                      ]}
                      dataSource={result.camera_results.map((r, i) => ({ ...r, key: i }))}
                      pagination={false}
                      size="small"
                    />

                    {/* 各机位检测叠加图 */}
                    <Typography.Title level={5} className="mt-4">
                      Detection Images
                    </Typography.Title>
                    <div
                      style={{
                        display: "flex",
                        gap: 16,
                        flexWrap: "wrap",
                        justifyContent: "flex-start",
                      }}
                    >
                      {result.camera_results.map((r) =>
                        r.overlay_image_base64 ? (
                          <Card
                            key={r.camera_id}
                            size="small"
                            title={`${r.camera_id}`}
                            extra={<Tag color={statusColor(r.status)}>{r.status}</Tag>}
                            style={{ width: 420 }}
                            styles={{ body: { padding: 0 } }}
                          >
                            <img
                              src={`data:image/jpeg;base64,${r.overlay_image_base64}`}
                              alt={`${r.camera_id} overlay`}
                              style={{
                                width: "100%",
                                maxHeight: 400,
                                objectFit: "contain",
                                display: "block",
                              }}
                            />
                          </Card>
                        ) : null,
                      )}
                    </div>
                  </>
                )}
              </>
            )}

            {!taskId && !result && (
              <div className="text-center py-8">
                <ScanOutlined className="text-4xl text-gray-300 block mb-3" />
                <Typography.Text type="secondary">
                  上传图像并点击 Run Inspection 开始检测
                </Typography.Text>
              </div>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
