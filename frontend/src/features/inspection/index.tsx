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
  Steps,
  Result,
} from "antd";
import {
  PlayCircleOutlined,
  InboxOutlined,
  ScanOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import PageHeader from "../../components/ui/PageHeader";
import { PhotoProvider, PhotoView } from "react-photo-view";
import "react-photo-view/dist/react-photo-view.css";
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

  const getCurrentStep = () => {
    if (!taskId) return 0;
    if (!result) return 1;
    if (result.status === "PENDING" || result.status === "STARTED") return 1;
    return 2;
  };

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

      <Steps
        current={getCurrentStep()}
        size="small"
        className="mb-6"
        items={[
          { title: "配置", description: "选择型号与相机" },
          { title: "上传检测", description: "上传图像并运行" },
          { title: "结果", description: "查看检测结果" },
        ]}
      />

      <Row gutter={24}>
        {/* 左侧：配置区 */}
        <Col span={10}>
          <Card title={<Space><ScanOutlined />检测配置</Space>}>
            <Typography.Text strong>1. 选择座椅型号</Typography.Text>
            <Select
              className="w-full mt-1 mb-4"
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
                  className="w-full mt-1 mb-4"
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
                  <div key={slot.cameraId} className="mb-3 p-3 border border-gray-200 rounded-lg">
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
              <div className="text-center py-10">
                <Spin size="large" />
                <div className="mt-3 text-gray-400">检测运行中，请稍候...</div>
              </div>
            )}

            {result && !isRunning && (
              <>
                <Descriptions column={2} size="small" bordered className="mb-4">
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
                  <Typography.Text type="danger" className="block mb-4">
                    {result.error_message}
                  </Typography.Text>
                )}

                {result.overall_status && !isRunning && (
                  <Result
                    status={result.overall_status === "OK" ? "success" : "error"}
                    title={result.overall_status === "OK" ? "检测通过" : "检测异常"}
                    subTitle={result.decision_reason ?? ""}
                  />
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
                                <span className="text-xs">{v.toFixed(4)}</span>
                                <Progress
                                  percent={Math.min(v * 100, 100)}
                                  showInfo={false}
                                  size="small"
                                  strokeColor={v > 0.5 ? "#ff4d4f" : "#52c41a"}
                                  className="w-12 inline-block"
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

                    <Typography.Title level={5} className="mt-4">检测图像</Typography.Title>
                    <PhotoProvider>
                      <div className="flex gap-4 flex-wrap">
                        {result.camera_results.map((r) =>
                          r.overlay_image_base64 ? (
                            <Card
                              key={r.camera_id}
                              size="small"
                              title={r.camera_id}
                              extra={<Tag color={statusColor(r.status)}>{r.status}</Tag>}
                              className="w-[420px]"
                              styles={{ body: { padding: 0 } }}
                            >
                              <PhotoView src={`data:image/jpeg;base64,${r.overlay_image_base64}`}>
                                <img
                                  src={`data:image/jpeg;base64,${r.overlay_image_base64}`}
                                  alt={`${r.camera_id} overlay`}
                                  className="w-full max-h-[400px] object-contain block cursor-zoom-in"
                                />
                              </PhotoView>
                            </Card>
                          ) : null,
                        )}
                      </div>
                    </PhotoProvider>
                  </>
                )}
              </>
            )}

            {!taskId && !result && (
              <div className="text-center py-10">
                <ScanOutlined className="text-[40px] text-gray-300 block mb-3" />
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
