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
  Space,
  Typography,
  Divider,
} from "antd";
import {
  UploadOutlined,
  InboxOutlined,
} from "@ant-design/icons";
import PageHeader from "../../components/ui/PageHeader";
import { anomalyApi } from "../../api";

const { Dragger } = Upload;
const { Title } = Typography;

export default function AnomalyUploadPage() {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const handleJsonSubmit = async (values: Record<string, unknown>) => {
    setLoading(true);
    try {
      const res = await anomalyApi.upload({
        camera_id: values.camera_id as string,
        source: values.source as string,
        anomaly_score: values.anomaly_score as number | undefined,
        date_folder: values.date_folder as string,
        detected_at: values.detected_at as string,
        metadata: values.metadata ? JSON.parse(values.metadata as string) : undefined,
      });
      setResult(res.anomaly_id);
    } catch {
      message.error("Upload failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Anomaly Upload"
        extra={
          <Button
            type="primary"
            onClick={() => form.submit()}
            loading={loading}
            icon={<UploadOutlined />}
          >
            Submit Metadata
          </Button>
        }
      />

      {result && (
        <Card className="mb-4" type="inner">
          <Typography.Text strong>Anomaly registered: </Typography.Text>
          <Typography.Text code>{result}</Typography.Text>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="JSON Metadata Upload">
          <Form
            form={form}
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
          </Form>
        </Card>

        <Card title="File Upload (via API)">
          <Typography.Paragraph type="secondary">
            Use the <Typography.Text code>POST /api/anomaly/upload-with-files</Typography.Text> endpoint
            to upload anomaly images alongside metadata. This endpoint accepts multipart form data.
          </Typography.Paragraph>
          <Divider />
          <Typography.Paragraph>
            For now, you can use <Typography.Text code>curl</Typography.Text> or a REST client:
          </Typography.Paragraph>
          <pre className="bg-gray-900 text-green-400 p-3 rounded text-xs overflow-auto">
{`curl -X POST http://localhost:8000/api/anomaly/upload-with-files \\
  -F "camera_id=left_top" \\
  -F "source=patchcore" \\
  -F "date_folder=2025-01-15" \\
  -F "detected_at=2025-01-15T10:30:00" \\
  -F "anomaly_score=0.87" \\
  -F "crop_file=@/path/to/crop.jpg" \\
  -F "original_file=@/path/to/original.jpg"`}
          </pre>
        </Card>
      </div>
    </div>
  );
}
