import { useState } from "react";
import {
  Card,
  Form,
  Input,
  Select,
  InputNumber,
  DatePicker,
  Button,
  Upload,
  message,
  Typography,
  Divider,
  Space,
} from "antd";
import { UploadOutlined } from "@ant-design/icons";
import type { UploadFile } from "antd";
import dayjs from "dayjs";
import PageHeader from "../../components/ui/PageHeader";
import { anomalyApi } from "../../api";

const { Title } = Typography;

export default function AnomalyUploadPage() {
  const [jsonLoading, setJsonLoading] = useState(false);
  const [fileLoading, setFileLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [jsonForm] = Form.useForm();
  const [fileForm] = Form.useForm();
  const [fileList, setFileList] = useState<Record<string, UploadFile[]>>({});

  const handleJsonSubmit = async (values: Record<string, unknown>) => {
    setJsonLoading(true);
    try {
      const res = await anomalyApi.upload({
        camera_id: values.camera_id as string,
        source: values.source as string,
        anomaly_score: values.anomaly_score as number | undefined,
        date_folder: values.date_folder as string,
        detected_at:
          values.detected_at instanceof dayjs
            ? (values.detected_at as dayjs.Dayjs).toISOString()
            : (values.detected_at as string),
        metadata: values.metadata ? JSON.parse(values.metadata as string) : undefined,
      });
      setResult(res.anomaly_id);
      message.success(`Anomaly registered: ${res.anomaly_id}`);
    } catch {
      message.error("Upload failed");
    } finally {
      setJsonLoading(false);
    }
  };

  const handleFileUpload = async (values: Record<string, unknown>) => {
    setFileLoading(true);
    try {
      const formData = new FormData();
      formData.append("camera_id", values.camera_id as string);
      formData.append("source", (values.source as string) || "patchcore");
      formData.append("date_folder", values.date_folder as string);
      formData.append(
        "detected_at",
        values.detected_at instanceof dayjs
          ? (values.detected_at as dayjs.Dayjs).toISOString()
          : (values.detected_at as string),
      );
      if (values.anomaly_score != null) {
        formData.append("anomaly_score", String(values.anomaly_score));
      }

      const fileFields = ["original_file", "roi_file", "heatmap_file", "crop_file"];
      for (const field of fileFields) {
        const files = fileList[field];
        if (files && files.length > 0 && files[0].originFileObj) {
          formData.append(field, files[0].originFileObj as File);
        }
      }

      const res = await anomalyApi.uploadWithFiles(formData);
      setResult(res.anomaly_id);
      message.success(`Anomaly with files registered: ${res.anomaly_id}`);
    } catch {
      message.error("File upload failed");
    } finally {
      setFileLoading(false);
    }
  };

  const handleFileChange =
    (field: string) =>
    ({ fileList: newList }: { fileList: UploadFile[] }) => {
      setFileList((prev) => ({ ...prev, [field]: newList }));
    };

  const renderFileUpload = (field: string, label: string) => (
    <Form.Item label={label}>
      <Upload
        maxCount={1}
        beforeUpload={() => false}
        fileList={fileList[field] || []}
        onChange={handleFileChange(field)}
        accept="image/jpeg,image/png"
      >
        <Button icon={<UploadOutlined />}>Select {label}</Button>
      </Upload>
    </Form.Item>
  );

  return (
    <div>
      <PageHeader title="Anomaly Upload" />

      {result && (
        <Card className="mb-4" type="inner">
          <Typography.Text strong>Anomaly registered: </Typography.Text>
          <Typography.Text code>{result}</Typography.Text>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="JSON Metadata Upload">
          <Form
            form={jsonForm}
            layout="vertical"
            onFinish={handleJsonSubmit}
            initialValues={{ source: "patchcore" }}
          >
            <Form.Item
              name="camera_id"
              label="Camera ID"
              rules={[{ required: true, message: "Camera ID is required" }]}
            >
              <Input placeholder="e.g. camera_left_top" />
            </Form.Item>

            <Form.Item name="source" label="Source" rules={[{ required: true }]}>
              <Select
                options={[
                  { value: "patchcore", label: "PatchCore" },
                  { value: "filter_classifier", label: "Filter Classifier" },
                  { value: "rule_engine", label: "Rule Engine" },
                ]}
              />
            </Form.Item>

            <Form.Item name="anomaly_score" label="Anomaly Score">
              <InputNumber min={0} max={1} step={0.01} className="w-full" />
            </Form.Item>

            <Form.Item
              name="date_folder"
              label="Date Folder"
              rules={[{ required: true, message: "Date folder is required" }]}
            >
              <Input placeholder="YYYY-MM-DD" />
            </Form.Item>

            <Form.Item
              name="detected_at"
              label="Detected At"
              rules={[{ required: true, message: "Detection time is required" }]}
            >
              <DatePicker showTime className="w-full" />
            </Form.Item>

            <Form.Item name="metadata" label="Metadata (JSON)">
              <Input.TextArea rows={3} placeholder='{"key": "value"}' />
            </Form.Item>

            <Form.Item>
              <Button
                type="primary"
                htmlType="submit"
                loading={jsonLoading}
                icon={<UploadOutlined />}
              >
                Submit Metadata
              </Button>
            </Form.Item>
          </Form>
        </Card>

        <Card title="Multipart File Upload">
          <Form
            form={fileForm}
            layout="vertical"
            onFinish={handleFileUpload}
            initialValues={{ source: "patchcore" }}
          >
            <Form.Item
              name="camera_id"
              label="Camera ID"
              rules={[{ required: true, message: "Camera ID is required" }]}
            >
              <Input placeholder="e.g. camera_left_top" />
            </Form.Item>

            <Form.Item name="source" label="Source" rules={[{ required: true }]}>
              <Select
                options={[
                  { value: "patchcore", label: "PatchCore" },
                  { value: "filter_classifier", label: "Filter Classifier" },
                  { value: "rule_engine", label: "Rule Engine" },
                ]}
              />
            </Form.Item>

            <Form.Item name="anomaly_score" label="Anomaly Score">
              <InputNumber min={0} max={1} step={0.01} className="w-full" />
            </Form.Item>

            <Form.Item
              name="date_folder"
              label="Date Folder"
              rules={[{ required: true, message: "Date folder is required" }]}
            >
              <Input placeholder="YYYY-MM-DD" />
            </Form.Item>

            <Form.Item
              name="detected_at"
              label="Detected At"
              rules={[{ required: true, message: "Detection time is required" }]}
            >
              <DatePicker showTime className="w-full" />
            </Form.Item>

            <Divider plain>Image Files (optional)</Divider>

            {renderFileUpload("original_file", "Original Image")}
            {renderFileUpload("roi_file", "ROI Image")}
            {renderFileUpload("heatmap_file", "Heatmap Image")}
            {renderFileUpload("crop_file", "Crop Image")}

            <Form.Item>
              <Button
                type="primary"
                htmlType="submit"
                loading={fileLoading}
                icon={<UploadOutlined />}
              >
                Upload with Files
              </Button>
            </Form.Item>
          </Form>
        </Card>
      </div>
    </div>
  );
}
