import { useState } from "react";
import {
  Card,
  Table,
  Button,
  Modal,
  Form,
  Input,
  InputNumber,
  Select,
  Switch,
  Space,
  message,
  Typography,
  Row,
  Col,
  List,
  Tag,
  Popconfirm,
} from "antd";
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  SettingOutlined,
} from "@ant-design/icons";
import PageHeader from "../../components/ui/PageHeader";
import {
  useSeatModels,
  useCreateSeatModel,
  useUpdateSeatModel,
  useDeleteSeatModel,
  useCameras,
  useCreateCamera,
  useUpdateCamera,
  useDeleteCamera,
  useModelOptions,
  useRegisterModel,
} from "../../hooks/queries";
import type {
  CameraConfigFormData,
  SeatModelFormData,
  SeatModel,
  CameraConfig,
  ModelOption,
  ModelRegisterData,
} from "../../types";

const PAGE_SIZE = 20;

/** 根据 model_version_id 查找模型显示文本 */
function modelLabel(
  modelVersionId: string | null,
  models: ModelOption[],
): string {
  if (!modelVersionId) return "-";
  const m = models.find((opt) => opt.model_id === modelVersionId);
  return m ? `${m.model_name} (${m.version})` : modelVersionId;
}

export default function CameraConfigPage() {
  const [page, setPage] = useState(1);
  const [selectedSeatModel, setSelectedSeatModel] = useState<string | null>(null);
  const [seatModalOpen, setSeatModalOpen] = useState(false);
  const [editingSeat, setEditingSeat] = useState<SeatModel | null>(null);
  const [cameraModalOpen, setCameraModalOpen] = useState(false);
  const [editingCamera, setEditingCamera] = useState<CameraConfig | null>(null);
  const [registerModalOpen, setRegisterModalOpen] = useState(false);
  const [seatForm] = Form.useForm<SeatModelFormData>();
  const [cameraForm] = Form.useForm<CameraConfigFormData>();
  const [registerForm] = Form.useForm<ModelRegisterData>();

  const { data: seatModels, isLoading: seatLoading } = useSeatModels(page, PAGE_SIZE);
  const { data: cameras, isLoading: camerasLoading } = useCameras(selectedSeatModel);

  // 按类型分别获取模型下拉选项
  const { data: yoloModels } = useModelOptions("yolo");
  const { data: patchcoreModels } = useModelOptions("patchcore");
  const { data: filterClassifierModels } = useModelOptions("filter_classifier");
  // 合并所有模型用于表格展示
  const allModels = [
    ...(yoloModels ?? []),
    ...(patchcoreModels ?? []),
    ...(filterClassifierModels ?? []),
  ];

  const createSeatMut = useCreateSeatModel();
  const updateSeatMut = useUpdateSeatModel();
  const deleteSeatMut = useDeleteSeatModel();
  const createCamMut = useCreateCamera();
  const updateCamMut = useUpdateCamera();
  const deleteCamMut = useDeleteCamera();
  const registerModelMut = useRegisterModel();

  // ── Seat Model handlers ──
  const openSeatCreate = () => {
    setEditingSeat(null);
    seatForm.resetFields();
    setSeatModalOpen(true);
  };

  const openSeatEdit = (record: SeatModel) => {
    setEditingSeat(record);
    seatForm.setFieldsValue({
      seat_model_id: record.seat_model_id,
      display_name: record.display_name,
    });
    setSeatModalOpen(true);
  };

  const handleSeatSubmit = async () => {
    const values = await seatForm.validateFields();
    if (editingSeat) {
      await updateSeatMut.mutateAsync({ id: editingSeat.id, data: values });
      message.success("座椅型号已更新");
    } else {
      await createSeatMut.mutateAsync(values);
      message.success("座椅型号已创建");
    }
    setSeatModalOpen(false);
  };

  const handleSeatDelete = async (id: string) => {
    await deleteSeatMut.mutateAsync(id);
    if (
      selectedSeatModel &&
      seatModels?.find((s) => s.id === id)?.seat_model_id === selectedSeatModel
    ) {
      setSelectedSeatModel(null);
    }
    message.success("座椅型号已删除");
  };

  // ── Camera Config handlers ──
  const openCameraCreate = () => {
    setEditingCamera(null);
    cameraForm.resetFields();
    cameraForm.setFieldsValue({
      detection_confidence: 0.25,
      patchcore_image_size: 256,
      patchcore_threshold: 0.99,
      region_mode_enabled: false,
      patchcore_model_version_id: null,
      yolo_model_version_id: null,
      filter_classifier_model_version_id: null,
      region_upper_model_version_id: null,
      region_middle_model_version_id: null,
      region_lower_model_version_id: null,
    });
    setCameraModalOpen(true);
  };

  const openCameraEdit = (record: CameraConfig) => {
    setEditingCamera(record);
    cameraForm.setFieldsValue({
      camera_id: record.camera_id,
      patchcore_model_version_id: record.patchcore_model_version_id,
      yolo_model_version_id: record.yolo_model_version_id,
      filter_classifier_model_version_id: record.filter_classifier_model_version_id,
      detection_confidence: record.detection_confidence,
      patchcore_image_size: record.patchcore_image_size,
      patchcore_threshold: record.patchcore_threshold,
      region_mode_enabled: record.region_mode_enabled,
      region_upper_model_version_id: record.region_upper_model_version_id,
      region_middle_model_version_id: record.region_middle_model_version_id,
      region_lower_model_version_id: record.region_lower_model_version_id,
    });
    setCameraModalOpen(true);
  };

  const handleCameraSubmit = async () => {
    const values = await cameraForm.validateFields();
    if (!selectedSeatModel) {
      message.error("请先选择一个座椅型号");
      return;
    }
    if (editingCamera) {
      await updateCamMut.mutateAsync({
        seatModelId: selectedSeatModel,
        cameraDbId: editingCamera.id,
        data: values,
      });
      message.success("相机配置已更新");
    } else {
      await createCamMut.mutateAsync({
        seatModelId: selectedSeatModel,
        data: values,
      });
      message.success("相机配置已创建");
    }
    setCameraModalOpen(false);
  };

  const handleCameraDelete = async (cameraDbId: string) => {
    if (!selectedSeatModel) return;
    await deleteCamMut.mutateAsync({ seatModelId: selectedSeatModel, cameraDbId });
    message.success("相机配置已删除");
  };

  // ── Model Register handlers ──
  const handleRegisterModel = async () => {
    const values = await registerForm.validateFields();
    await registerModelMut.mutateAsync(values);
    message.success("模型注册成功");
    setRegisterModalOpen(false);
    registerForm.resetFields();
  };

  const regionModeEnabled = Form.useWatch("region_mode_enabled", cameraForm);

  // 模型选择器通用 props
  const yoloSelectProps = {
    showSearch: true,
    optionFilterProp: "label" as const,
    placeholder: "选择 YOLO 模型",
    allowClear: true,
    loading: !yoloModels,
    options: (yoloModels ?? []).map((m) => ({
      label: `${m.model_name} (${m.version})`,
      value: m.model_id,
    })),
  };

  const patchcoreSelectProps = {
    showSearch: true,
    optionFilterProp: "label" as const,
    placeholder: "选择 PatchCore 模型",
    allowClear: true,
    loading: !patchcoreModels,
    options: (patchcoreModels ?? []).map((m) => ({
      label: `${m.model_name} (${m.version})`,
      value: m.model_id,
    })),
  };

  const filterClassifierSelectProps = {
    showSearch: true,
    optionFilterProp: "label" as const,
    placeholder: "选择 Filter Classifier 模型（可选）",
    allowClear: true,
    loading: !filterClassifierModels,
    options: (filterClassifierModels ?? []).map((m) => ({
      label: `${m.model_name} (${m.version})`,
      value: m.model_id,
    })),
  };

  return (
    <div>
      <PageHeader title="相机配置" />

      <Row gutter={24}>
        {/* 左侧：座椅型号列表 */}
        <Col span={8}>
          <Card
            title="座椅型号"
            extra={
              <Button icon={<PlusOutlined />} size="small" onClick={openSeatCreate}>
                新建
              </Button>
            }
          >
            <List
              loading={seatLoading}
              dataSource={seatModels ?? []}
              renderItem={(item) => (
                <List.Item
                  onClick={() => setSelectedSeatModel(item.seat_model_id)}
                  style={{
                    cursor: "pointer",
                    padding: "4px 8px",
                    borderRadius: 4,
                    background:
                      selectedSeatModel === item.seat_model_id ? "#e6f4ff" : undefined,
                  }}
                  actions={[
                    <Button
                      key="edit"
                      type="link"
                      size="small"
                      icon={<EditOutlined />}
                      onClick={(e) => {
                        e.stopPropagation();
                        openSeatEdit(item);
                      }}
                    />,
                    <Popconfirm
                      key="delete"
                      title="确定删除此座椅型号？"
                      onConfirm={() => handleSeatDelete(item.id)}
                    >
                      <Button
                        type="link"
                        size="small"
                        danger
                        icon={<DeleteOutlined />}
                        onClick={(e) => e.stopPropagation()}
                      />
                    </Popconfirm>,
                  ]}
                >
                  <List.Item.Meta
                    title={item.display_name}
                    description={item.seat_model_id}
                  />
                </List.Item>
              )}
            />
          </Card>
        </Col>

        {/* 右侧：相机配置表格 */}
        <Col span={16}>
          <Card
            title={
              selectedSeatModel
                ? `相机列表 — ${selectedSeatModel}`
                : "请选择左侧座椅型号"
            }
            extra={
              selectedSeatModel && (
                <Space>
                  <Button icon={<PlusOutlined />} size="small" onClick={openCameraCreate}>
                    添加相机
                  </Button>
                  <Button size="small" onClick={() => setRegisterModalOpen(true)}>
                    注册模型
                  </Button>
                </Space>
              )
            }
          >
            {!selectedSeatModel && (
              <div style={{ textAlign: "center", padding: "40px 0" }}>
                <SettingOutlined
                  style={{ fontSize: 40, color: "#d9d9d9", display: "block", marginBottom: 12 }}
                />
                <Typography.Text type="secondary">
                  请先选择左侧座椅型号
                </Typography.Text>
              </div>
            )}

            {selectedSeatModel && (
              <Table
                columns={[
                  { title: "相机ID", dataIndex: "camera_id", width: 120 },
                  {
                    title: "YOLO 模型",
                    dataIndex: "yolo_model_version_id",
                    width: 200,
                    ellipsis: true,
                    render: (v: string | null) => modelLabel(v, allModels),
                  },
                  {
                    title: "PatchCore 模型",
                    dataIndex: "patchcore_model_version_id",
                    width: 200,
                    ellipsis: true,
                    render: (v: string | null) => modelLabel(v, allModels),
                  },
                  {
                    title: "Filter Classifier",
                    dataIndex: "filter_classifier_model_version_id",
                    width: 180,
                    ellipsis: true,
                    render: (v: string | null) => modelLabel(v, allModels),
                  },
                  {
                    title: "Region 模式",
                    dataIndex: "region_mode_enabled",
                    width: 100,
                    render: (v: boolean) => (
                      <Tag color={v ? "blue" : "default"}>
                        {v ? "三分区" : "整体"}
                      </Tag>
                    ),
                  },
                  {
                    title: "操作",
                    width: 120,
                    render: (_: unknown, record: CameraConfig) => (
                      <Space>
                        <Button
                          size="small"
                          icon={<EditOutlined />}
                          onClick={() => openCameraEdit(record)}
                        />
                        <Popconfirm
                          title="确定删除此相机配置？"
                          onConfirm={() => handleCameraDelete(record.id)}
                        >
                          <Button size="small" danger icon={<DeleteOutlined />} />
                        </Popconfirm>
                      </Space>
                    ),
                  },
                ]}
                dataSource={cameras ?? []}
                rowKey="id"
                loading={camerasLoading}
                pagination={false}
                size="small"
              />
            )}
          </Card>
        </Col>
      </Row>

      {/* 座椅型号 Modal */}
      <Modal
        title={editingSeat ? "编辑座椅型号" : "新建座椅型号"}
        open={seatModalOpen}
        onOk={handleSeatSubmit}
        onCancel={() => setSeatModalOpen(false)}
        confirmLoading={createSeatMut.isPending || updateSeatMut.isPending}
        destroyOnClose
      >
        <Form form={seatForm} layout="vertical">
          <Form.Item
            name="seat_model_id"
            label="座椅型号 ID"
            rules={[{ required: true, message: "请输入座椅型号 ID" }]}
          >
            <Input placeholder="如 seat_model_a" disabled={!!editingSeat} />
          </Form.Item>
          <Form.Item
            name="display_name"
            label="显示名称"
            rules={[{ required: true, message: "请输入显示名称" }]}
          >
            <Input placeholder="如 座椅型号A" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 相机配置 Modal */}
      <Modal
        title={editingCamera ? "编辑相机配置" : "新建相机配置"}
        open={cameraModalOpen}
        onOk={handleCameraSubmit}
        onCancel={() => setCameraModalOpen(false)}
        confirmLoading={createCamMut.isPending || updateCamMut.isPending}
        width={640}
        destroyOnClose
      >
        <Form form={cameraForm} layout="vertical">
          <Form.Item
            name="camera_id"
            label="相机 ID"
            rules={[{ required: true, message: "请输入相机 ID" }]}
          >
            <Input placeholder="如 cam_back" disabled={!!editingCamera} />
          </Form.Item>
          <Form.Item
            name="yolo_model_version_id"
            label="YOLO 检测模型"
            rules={[{ required: true, message: "请选择 YOLO 模型" }]}
          >
            <Select {...yoloSelectProps} />
          </Form.Item>
          <Form.Item
            name="patchcore_model_version_id"
            label="PatchCore 模型"
            rules={[{ required: true, message: "请选择 PatchCore 模型" }]}
          >
            <Select {...patchcoreSelectProps} />
          </Form.Item>
          <Form.Item
            name="filter_classifier_model_version_id"
            label="Filter Classifier 模型"
          >
            <Select {...filterClassifierSelectProps} />
          </Form.Item>

          <Typography.Title level={5}>高级参数</Typography.Title>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="detection_confidence" label="YOLO 置信度">
                <InputNumber min={0} max={1} step={0.05} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="patchcore_image_size" label="PatchCore 图像尺寸">
                <InputNumber min={64} max={1024} step={32} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="patchcore_threshold" label="PatchCore 阈值">
                <InputNumber min={0} max={1} step={0.01} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="region_mode_enabled"
            label="Region 分区模式"
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>

          {regionModeEnabled && (
            <>
              <Form.Item
                name="region_upper_model_version_id"
                label="Upper 区域模型"
                rules={[{ required: true, message: "请选择 upper 区域模型" }]}
              >
                <Select {...patchcoreSelectProps} placeholder="选择 upper 区域 PatchCore 模型" />
              </Form.Item>
              <Form.Item
                name="region_middle_model_version_id"
                label="Middle 区域模型"
                rules={[{ required: true, message: "请选择 middle 区域模型" }]}
              >
                <Select {...patchcoreSelectProps} placeholder="选择 middle 区域 PatchCore 模型" />
              </Form.Item>
              <Form.Item
                name="region_lower_model_version_id"
                label="Lower 区域模型"
                rules={[{ required: true, message: "请选择 lower 区域模型" }]}
              >
                <Select {...patchcoreSelectProps} placeholder="选择 lower 区域 PatchCore 模型" />
              </Form.Item>
            </>
          )}
        </Form>
      </Modal>

      {/* 模型注册 Modal */}
      <Modal
        title="注册模型"
        open={registerModalOpen}
        onOk={handleRegisterModel}
        onCancel={() => {
          setRegisterModalOpen(false);
          registerForm.resetFields();
        }}
        confirmLoading={registerModelMut.isPending}
        destroyOnClose
      >
        <Form form={registerForm} layout="vertical">
          <Form.Item
            name="model_name"
            label="模型名称"
            rules={[{ required: true, message: "请输入模型名称" }]}
          >
            <Input placeholder="如 yolo_seat_v3" />
          </Form.Item>
          <Form.Item
            name="version"
            label="版本"
            rules={[{ required: true, message: "请输入版本号" }]}
          >
            <Input placeholder="如 v1.0" />
          </Form.Item>
          <Form.Item
            name="model_type"
            label="模型类型"
            rules={[{ required: true, message: "请选择模型类型" }]}
          >
            <Select
              placeholder="选择模型类型"
              options={[
                { label: "YOLO", value: "yolo" },
                { label: "PatchCore", value: "patchcore" },
                { label: "Filter Classifier", value: "filter_classifier" },
                { label: "Embedding", value: "embedding" },
              ]}
            />
          </Form.Item>
          <Form.Item
            name="artifact_path"
            label="模型文件路径"
            rules={[{ required: true, message: "请输入模型文件的绝对路径" }]}
            extra="请输入本地文件系统的绝对路径，推理时直接从此路径加载"
          >
            <Input placeholder="/data/models/yolo/best.pt" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
