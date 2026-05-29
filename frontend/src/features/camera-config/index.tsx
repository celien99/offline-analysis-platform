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
  WarningOutlined,
  CheckCircleOutlined,
} from "@ant-design/icons";
import PageHeader from "../../components/ui/PageHeader";
import CameraTopology from "./components/CameraTopology";
import ModelSelect from "./components/ModelSelect";
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
  useImportBatchTrain,
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
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [importResult, setImportResult] = useState<Record<string, unknown> | null>(null);
  const [seatForm] = Form.useForm<SeatModelFormData>();
  const [cameraForm] = Form.useForm<CameraConfigFormData>();
  const [registerForm] = Form.useForm<ModelRegisterData>();
  const [importForm] = Form.useForm<{ output_root: string }>();

  const { data: seatModels, isLoading: seatLoading } = useSeatModels(page, PAGE_SIZE);
  const { data: cameras, isLoading: camerasLoading } = useCameras(selectedSeatModel);

  // 按类型分别获取模型下拉选项
  const { data: yoloModels } = useModelOptions("yolo");
  const { data: efficientadModels } = useModelOptions("efficientad");
  const { data: filterClassifierModels } = useModelOptions("filter_classifier");
  const { data: projectorModels } = useModelOptions("projector");
  const { data: whiteningMatrixModels } = useModelOptions("whitening_matrix");
  const { data: normalizerModels } = useModelOptions("camera_normalizer");
  // 合并所有模型用于表格展示
  const allModels = [
    ...(yoloModels ?? []),
    ...(efficientadModels ?? []),
    ...(filterClassifierModels ?? []),
    ...(projectorModels ?? []),
    ...(whiteningMatrixModels ?? []),
    ...(normalizerModels ?? []),
  ];

  const createSeatMut = useCreateSeatModel();
  const updateSeatMut = useUpdateSeatModel();
  const deleteSeatMut = useDeleteSeatModel();
  const createCamMut = useCreateCamera();
  const updateCamMut = useUpdateCamera();
  const deleteCamMut = useDeleteCamera();
  const registerModelMut = useRegisterModel();
  const importBatchTrainMut = useImportBatchTrain();

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
      yolo_model_version_id: record.yolo_model_version_id,
      projector_model_version_id: record.projector_model_version_id,
      whitening_matrix_model_version_id: record.whitening_matrix_model_version_id,
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
      efficientad_image_size: 256,
      efficientad_threshold: 0.99,
      efficientad_model_version_id: null,
      filter_classifier_model_version_id: null,
      normalizer_model_version_id: null,
    });
    setCameraModalOpen(true);
  };

  const openCameraEdit = (record: CameraConfig) => {
    setEditingCamera(record);
    cameraForm.setFieldsValue({
      camera_id: record.camera_id,
      efficientad_model_version_id: record.efficientad_model_version_id,
      filter_classifier_model_version_id: record.filter_classifier_model_version_id,
      normalizer_model_version_id: record.normalizer_model_version_id,
      detection_confidence: record.detection_confidence,
      efficientad_image_size: record.efficientad_image_size,
      efficientad_threshold: record.efficientad_threshold,
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

  const handleImportBatchTrain = async () => {
    if (!selectedSeatModel) {
      message.error("请先选择左侧座椅型号");
      return;
    }
    const values = await importForm.validateFields();
    try {
      const result = await importBatchTrainMut.mutateAsync({
        output_root: values.output_root,
        seat_model_id: selectedSeatModel,
        auto_bind: true,
      });
      setImportResult(result as unknown as Record<string, unknown>);
      message.success(
        `导入完成: ${(result as unknown as Record<string, unknown>).imported instanceof Array ? (result as unknown as { imported: unknown[] }).imported.length : 0} 个模型`
      );
    } catch {
      // error handled by mutation
    }
  };

  // ── 当前选中 SeatModel 的派生数据 ──
  const activeSeatModel = (seatModels ?? []).find((s) => s.seat_model_id === selectedSeatModel) ?? null;
  const yoloLabel = modelLabel(activeSeatModel?.yolo_model_version_id ?? null, allModels);
  const projectorLabel = modelLabel(activeSeatModel?.projector_model_version_id ?? null, allModels);
  const whiteningLabel = modelLabel(activeSeatModel?.whitening_matrix_model_version_id ?? null, allModels);

  const cameraTopoData = (cameras ?? []).map((c) => ({
    cameraId: c.camera_id,
    efficientadModel: modelLabel(c.efficientad_model_version_id, allModels),
    normalizerModel: modelLabel(c.normalizer_model_version_id, allModels),
    filterModel: c.filter_classifier_model_version_id
      ? modelLabel(c.filter_classifier_model_version_id, allModels)
      : undefined,
  }));

  return (
    <div>
      <PageHeader title="相机配置" />

      <CameraTopology
        seatModelId={selectedSeatModel ?? ""}
        yoloModel={yoloLabel}
        projectorModel={projectorLabel}
        whiteningModel={whiteningLabel}
        cameras={cameraTopoData}
      />

      {/* 全局模型配置 Card — 选中 SeatModel 时展示 */}
      {activeSeatModel && (
        <Card
          title="全局模型配置"
          className="industrial-card mb-4"
          extra={
            <Button size="small" icon={<EditOutlined />} onClick={() => openSeatEdit(activeSeatModel)}>
              编辑
            </Button>
          }
        >
          <Row gutter={[24, 12]}>
            {[
              {
                label: "YOLO 检测模型",
                value: yoloLabel,
                required: true,
                color: "#1677ff",
              },
              {
                label: "Embedding Projector",
                value: projectorLabel,
                required: false,
                color: "#eb2f96",
              },
              {
                label: "Whitening Matrix",
                value: whiteningLabel,
                required: false,
                color: "#13c2c2",
              },
            ].map((item) => {
              const isConfigured = item.value !== "-";
              return (
                <Col span={8} key={item.label}>
                  <div
                    style={{
                      padding: "12px 16px",
                      borderRadius: 6,
                      border: `1px solid ${isConfigured ? item.color : "#d9d9d9"}`,
                      background: isConfigured ? `${item.color}08` : "#fafafa",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                      {isConfigured ? (
                        <CheckCircleOutlined style={{ color: item.color, fontSize: 14 }} />
                      ) : (
                        <WarningOutlined style={{ color: item.required ? "#ff4d4f" : "#d9d9d9", fontSize: 14 }} />
                      )}
                      <span style={{ fontSize: 12, color: "#8c8c8c" }}>
                        {item.label}
                        {item.required && <span style={{ color: "#ff4d4f", marginLeft: 2 }}>*</span>}
                      </span>
                    </div>
                    <div style={{
                      fontSize: 13,
                      fontWeight: isConfigured ? 500 : 400,
                      color: isConfigured ? "#262626" : "#bfbfbf",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}>
                      {isConfigured ? item.value : (item.required ? "未配置" : "未配置（可选）")}
                    </div>
                  </div>
                </Col>
              );
            })}
          </Row>
        </Card>
      )}

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
              renderItem={(item) => {
                const hasYolo = !!item.yolo_model_version_id;
                return (
                  <List.Item
                    onClick={() => setSelectedSeatModel(item.seat_model_id)}
                    style={{
                      cursor: "pointer",
                      padding: "6px 10px",
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
                      title={
                        <Space size={4}>
                          <span>{item.display_name}</span>
                          {hasYolo ? (
                            <Tag color="blue" style={{ fontSize: 10, lineHeight: "16px", margin: 0 }}>YOLO</Tag>
                          ) : (
                            <Tag color="red" style={{ fontSize: 10, lineHeight: "16px", margin: 0 }}>缺YOLO</Tag>
                          )}
                        </Space>
                      }
                      description={item.seat_model_id}
                    />
                  </List.Item>
                );
              }}
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
                  <Button
                    size="small"
                    onClick={() => {
                      importForm.resetFields();
                      setImportResult(null);
                      setImportModalOpen(true);
                    }}
                  >
                    导入训练产物
                  </Button>
                </Space>
              )
            }
          >
            {!selectedSeatModel && (
              <div className="text-center py-10">
                <SettingOutlined
                  className="text-[40px] text-gray-300 block mb-3"
                />
                <Typography.Text type="secondary">
                  请先选择左侧座椅型号
                </Typography.Text>
              </div>
            )}

            {selectedSeatModel && (
              <Table
                columns={[
                  { title: "相机ID", dataIndex: "camera_id", width: 100, ellipsis: true },
                  {
                    title: "EfficientAD 模型",
                    dataIndex: "efficientad_model_version_id",
                    width: 140,
                    ellipsis: true,
                    render: (v: string | null) => modelLabel(v, allModels),
                  },
                  {
                    title: "Normalizer",
                    dataIndex: "normalizer_model_version_id",
                    width: 110,
                    ellipsis: true,
                    render: (v: string | null) => modelLabel(v, allModels),
                  },
                  {
                    title: "Filter Classifier",
                    dataIndex: "filter_classifier_model_version_id",
                    width: 140,
                    ellipsis: true,
                    render: (v: string | null) => modelLabel(v, allModels),
                  },
                  {
                    title: "操作",
                    width: 100,
                    render: (_: unknown, record: CameraConfig) => (
                      <Space size="small">
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
                scroll={{ x: 760 }}
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
          <Typography.Title level={5}>全局模型配置</Typography.Title>
          <Form.Item
            name="yolo_model_version_id"
            label="YOLO 检测模型"
            rules={[{ required: true, message: "请选择全局 YOLO 模型" }]}
          >
            <ModelSelect models={yoloModels} />
          </Form.Item>
          <Form.Item
            name="projector_model_version_id"
            label="Embedding Projector 模型"
          >
            <ModelSelect models={projectorModels} />
          </Form.Item>
          <Form.Item
            name="whitening_matrix_model_version_id"
            label="Whitening Matrix 模型"
          >
            <ModelSelect models={whiteningMatrixModels} />
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
            name="efficientad_model_version_id"
            label="EfficientAD 模型"
            rules={[{ required: true, message: "请选择 EfficientAD 模型" }]}
          >
            <ModelSelect models={efficientadModels} />
          </Form.Item>
          <Form.Item
            name="normalizer_model_version_id"
            label="Camera Normalizer"
          >
            <ModelSelect models={normalizerModels} />
          </Form.Item>
          <Form.Item
            name="filter_classifier_model_version_id"
            label="Filter Classifier 模型"
          >
            <ModelSelect models={filterClassifierModels} />
          </Form.Item>

          <Typography.Title level={5}>高级参数</Typography.Title>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="detection_confidence" label="YOLO 置信度">
                <InputNumber min={0} max={1} step={0.05} className="w-full" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="efficientad_image_size" label="EfficientAD 图像尺寸">
                <InputNumber min={64} max={1024} step={32} className="w-full" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="efficientad_threshold" label="EfficientAD 阈值">
                <InputNumber min={0} max={1} step={0.01} className="w-full" />
              </Form.Item>
            </Col>
          </Row>
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
                { label: "EfficientAD", value: "efficientad" },
                { label: "Filter Classifier", value: "filter_classifier" },
                { label: "Camera Normalizer", value: "camera_normalizer" },
                { label: "Embedding", value: "embedding" },
                { label: "Embedding Projector", value: "projector" },
                { label: "Whitening Matrix", value: "whitening_matrix" },
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

      {/* 导入 batch_train 产物 Modal */}
      <Modal
        title="导入训练产物"
        open={importModalOpen}
        onOk={handleImportBatchTrain}
        onCancel={() => {
          setImportModalOpen(false);
          setImportResult(null);
          importForm.resetFields();
        }}
        confirmLoading={importBatchTrainMut.isPending}
        width={600}
        destroyOnClose
      >
        <Form form={importForm} layout="vertical">
          <Form.Item
            name="output_root"
            label="batch_train 输出目录"
            rules={[{ required: true, message: "请输入输出目录的绝对路径" }]}
            extra={
              <span>
                目录应包含 *_efficientad.pt, *_norm.npz, projector.npz 等文件。
                导入后将自动注册并绑定到当前座椅型号的同名相机。
              </span>
            }
          >
            <Input placeholder="/data/models/seat_model_a/" />
          </Form.Item>
        </Form>
        {importResult && (
          <div className="mt-3">
            <Typography.Text strong>导入结果:</Typography.Text>
            <div className="text-sm mt-1">
              {(importResult.imported as Array<Record<string, unknown>>)?.length > 0 ? (
                <ul className="list-disc pl-4">
                  {(importResult.imported as Array<Record<string, unknown>>).map(
                    (item: Record<string, unknown>, i: number) => (
                      <li key={i}>
                        {item.file as string} → {item.model_type as string}
                        {item.bound ? " (已绑定)" : " (未绑定)"}
                      </li>
                    )
                  )}
                </ul>
              ) : (
                <span className="text-gray-400">未发现可导入的模型文件</span>
              )}
              {(importResult.errors as string[])?.length > 0 && (
                <div className="mt-2 text-red-500">
                  {(importResult.errors as string[]).map((e: string, i: number) => (
                    <div key={i}>{e}</div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
