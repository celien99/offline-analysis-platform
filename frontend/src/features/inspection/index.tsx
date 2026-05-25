import { useState } from "react";
import {
  Card,
  Table,
  Button,
  Tag,
  Upload,
  Space,
  message,
  Typography,
  Descriptions,
  Row,
  Col,
  Progress,
  Spin,
  Select,
} from "antd";
import {
  PlayCircleOutlined,
  InboxOutlined,
  ScanOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import PageHeader from "../../components/ui/PageHeader";
import { useInspectionRun, useInspectionResult, useSeatModelOptions } from "../../hooks/queries";
import type { SeatModelOption } from "../../types";

const { Dragger } = Upload;

interface CameraSlot {
  cameraId: string;
  file: File | null;
}

export default function InspectionPage() {
  const [selectedSeatModel, setSelectedSeatModel] = useState<string | null>(null);
  const [selectedCameras, setSelectedCameras] = useState<string[]>([]);
  const [slots, setSlots] = useState<CameraSlot[]>([]);
  const [taskId, setTaskId] = useState<string | null>(null);

  const { data: seatModelOptions, isLoading: optionsLoading } = useSeatModelOptions();
  const runMutation = useInspectionRun();
  const { data: result } = useInspectionResult(taskId);

  // 找到当前选中座椅型号的配置
  const currentSeatModel: SeatModelOption | undefined = seatModelOptions?.find(
    (s) => s.seat_model_id === selectedSeatModel,
  );

  // 座椅型号切换时，自动生成相机槽位
  const handleSeatModelChange = (seatModelId: string) => {
    setSelectedSeatModel(seatModelId);
    const model = seatModelOptions?.find((s) => s.seat_model_id === seatModelId);
    if (model) {
      const allCameraIds = model.cameras.map((c) => c.camera_id);
      setSelectedCameras(allCameraIds);
      setSlots(allCameraIds.map((cid) => ({ cameraId: cid, file: null })));
    }
  };

  // 相机多选变化时更新槽位
  const handleCamerasChange = (cameraIds: string[]) => {
    setSelectedCameras(cameraIds);
    setSlots(
      cameraIds.map((cid) => {
        const existing = slots.find((s) => s.cameraId === cid);
        return existing ?? { cameraId: cid, file: null };
      }),
    );
  };

  const updateSlotFile = (cameraId: string, file: File | null) => {
    setSlots(slots.map((s) => (s.cameraId === cameraId ? { ...s, file } : s)));
  };

  const handleRun = () => {
    if (!selectedSeatModel) {
      message.error("请选择座椅型号");
      return;
    }
    const filled = slots.filter((s) => s.file);
    if (filled.length === 0) {
      message.error("请至少上传一张图像");
      return;
    }

    const formData = new FormData();
    formData.append("seat_model_id", selectedSeatModel);
    formData.append("camera_ids", filled.map((s) => s.cameraId).join(","));
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
    if (currentSeatModel) {
      setSlots(currentSeatModel.cameras.map((c) => ({ cameraId: c.camera_id, file: null })));
    }
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
        title="在线检测"
        extra={
          <Button icon={<ReloadOutlined />} onClick={handleReset} disabled={isRunning}>
            重置
          </Button>
        }
      />

      <Row gutter={24}>
        {/* 左侧：配置区 */}
        <Col span={10}>
          <Card title={<Space><ScanOutlined />检测配置</Space>}>
            <Typography.Text strong>1. 选择座椅型号</Typography.Text>
            <Select
              style={{ width: "100%", marginTop: 4, marginBottom: 16 }}
              placeholder="选择座椅型号"
              loading={optionsLoading}
              value={selectedSeatModel}
              onChange={handleSeatModelChange}
              disabled={isRunning}
              allowClear
              options={(seatModelOptions ?? []).map((s) => ({
                value: s.seat_model_id,
                label: `${s.display_name} (${s.seat_model_id})`,
              }))}
            />

            {currentSeatModel && (
              <>
                <Typography.Text strong>2. 选择相机</Typography.Text>
                <Select
                  style={{ width: "100%", marginTop: 4, marginBottom: 16 }}
                  mode="multiple"
                  placeholder="勾选检测相机"
                  value={selectedCameras}
                  onChange={handleCamerasChange}
                  disabled={isRunning}
                  options={currentSeatModel.cameras.map((c) => ({
                    value: c.camera_id,
                    label: c.camera_id,
                  }))}
                />
              </>
            )}

            {slots.length > 0 && (
              <>
                <Typography.Text strong>3. 上传图像</Typography.Text>
                {slots.map((slot) => (
                  <div key={slot.cameraId} style={{ marginBottom: 12, padding: 12, border: "1px solid #e5e7eb", borderRadius: 8 }}>
                    <Typography.Text strong>{slot.cameraId}</Typography.Text>
                    <Dragger
                      accept="image/*"
                      maxCount={1}
                      disabled={isRunning}
                      beforeUpload={(file) => {
                        updateSlotFile(slot.cameraId, file);
                        return false;
                      }}
                      onRemove={() => updateSlotFile(slot.cameraId, null)}
                      style={slot.file ? { borderColor: "#52c41a" } : undefined}
                    >
                      <p className="ant-upload-drag-icon"><InboxOutlined /></p>
                      <p className="ant-upload-text">
                        {slot.file ? slot.file.name : "点击或拖拽图像到此区域"}
                      </p>
                    </Dragger>
                  </div>
                ))}
              </>
            )}

            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              size="large"
              block
              onClick={handleRun}
              loading={runMutation.isPending}
              disabled={isRunning || !selectedSeatModel || slots.length === 0}
            >
              开始检测
            </Button>
          </Card>
        </Col>

        {/* 右侧：检测结果 */}
        <Col span={14}>
          <Card title="检测结果">
            {isRunning && (
              <div style={{ textAlign: "center", padding: "40px 0" }}>
                <Spin size="large" />
                <div style={{ marginTop: 12, color: "#999" }}>检测运行中，请稍候...</div>
              </div>
            )}

            {result && !isRunning && (
              <>
                <Descriptions column={2} size="small" bordered style={{ marginBottom: 16 }}>
                  <Descriptions.Item label="任务 ID" span={2}>
                    {result.task_id}
                  </Descriptions.Item>
                  <Descriptions.Item label="任务状态">
                    <Tag color={statusColor(result.status)}>{result.status}</Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="整体结果">
                    <Tag color={statusColor(result.overall_status ?? "")}>
                      {result.overall_status ?? "-"}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="决策原因" span={2}>
                    {result.decision_reason ?? "-"}
                  </Descriptions.Item>
                </Descriptions>

                {result.error_message && (
                  <Typography.Text type="danger" style={{ display: "block", marginBottom: 16 }}>
                    {result.error_message}
                  </Typography.Text>
                )}

                {result.camera_results.length > 0 && (
                  <>
                    <Typography.Title level={5}>各相机结果</Typography.Title>
                    <Table
                      columns={[
                        { title: "相机ID", dataIndex: "camera_id", width: 120 },
                        {
                          title: "状态",
                          dataIndex: "status",
                          width: 90,
                          render: (s: string) => <Tag color={statusColor(s)}>{s}</Tag>,
                        },
                        {
                          title: "异常分数",
                          dataIndex: "anomaly_score",
                          width: 120,
                          render: (v: number | null) =>
                            v != null ? (
                              <Space size={4}>
                                <span style={{ fontSize: 12 }}>{v.toFixed(4)}</span>
                                <Progress
                                  percent={Math.min(v * 100, 100)}
                                  showInfo={false}
                                  size="small"
                                  strokeColor={v > 0.5 ? "#ff4d4f" : "#52c41a"}
                                  style={{ width: 48, display: "inline-block" }}
                                />
                              </Space>
                            ) : "-",
                        },
                        {
                          title: "是否异常",
                          dataIndex: "is_anomaly",
                          width: 90,
                          render: (v: boolean | null) =>
                            v == null ? "-" : <Tag color={v ? "red" : "green"}>{v ? "是" : "否"}</Tag>,
                        },
                        { title: "原因", dataIndex: "decision_reason", ellipsis: true },
                      ]}
                      dataSource={result.camera_results.map((r, i) => ({ ...r, key: i }))}
                      pagination={false}
                      size="small"
                    />

                    <Typography.Title level={5} style={{ marginTop: 16 }}>检测图像</Typography.Title>
                    <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
                      {result.camera_results.map((r) =>
                        r.overlay_image_base64 ? (
                          <Card
                            key={r.camera_id}
                            size="small"
                            title={r.camera_id}
                            extra={<Tag color={statusColor(r.status)}>{r.status}</Tag>}
                            style={{ width: 420 }}
                            styles={{ body: { padding: 0 } }}
                          >
                            <img
                              src={`data:image/jpeg;base64,${r.overlay_image_base64}`}
                              alt={`${r.camera_id} overlay`}
                              style={{ width: "100%", maxHeight: 400, objectFit: "contain", display: "block" }}
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
              <div style={{ textAlign: "center", padding: "40px 0" }}>
                <ScanOutlined style={{ fontSize: 40, color: "#d9d9d9", display: "block", marginBottom: 12 }} />
                <Typography.Text type="secondary">
                  选择座椅型号和相机，上传图像后点击「开始检测」
                </Typography.Text>
              </div>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
