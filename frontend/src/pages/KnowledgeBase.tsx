import { useEffect, useState } from "react";
import {
  Card,
  Table,
  Tag,
  Button,
  Space,
  Row,
  Col,
  Input,
  Select,
  Modal,
  Form,
  message,
  Popconfirm,
  Typography,
  Descriptions,
} from "antd";
import {
  PlusOutlined,
  ReloadOutlined,
  SearchOutlined,
  DeleteOutlined,
  EyeOutlined,
  BookOutlined,
} from "@ant-design/icons";
import axios from "axios";

const { Text, Paragraph } = Typography;
const { TextArea } = Input;

interface KnowledgeEntry {
  knowledge_id: string;
  cluster_id: string | null;
  category: string;
  defect_type: string | null;
  title: string;
  description: string | null;
  action: string;
  camera_ids: string[];
  created_at: string;
}

const CATEGORY_OPTIONS = [
  { value: "defect", label: "Defect" },
  { value: "false_alarm", label: "False Alarm" },
  { value: "camera_issue", label: "Camera Issue" },
  { value: "lighting", label: "Lighting" },
  { value: "process", label: "Process" },
];

const DEFECT_OPTIONS = [
  { value: "wrinkle", label: "Wrinkle" },
  { value: "scratch", label: "Scratch" },
  { value: "reflection", label: "Reflection" },
  { value: "stain", label: "Stain" },
  { value: "seam_shift", label: "Seam Shift" },
];

const ACTION_OPTIONS = [
  { value: "ignore", label: "Ignore" },
  { value: "NG", label: "NG" },
  { value: "review_required", label: "Review Required" },
];

export default function KnowledgeBase() {
  const [entries, setEntries] = useState<KnowledgeEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [categoryFilter, setCategoryFilter] = useState<string | undefined>();
  const [defectFilter, setDefectFilter] = useState<string | undefined>();
  const [searchKeyword, setSearchKeyword] = useState("");
  const [createVisible, setCreateVisible] = useState(false);
  const [detailVisible, setDetailVisible] = useState(false);
  const [selectedEntry, setSelectedEntry] = useState<KnowledgeEntry | null>(null);
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);

  const loadEntries = async () => {
    setLoading(true);
    try {
      if (searchKeyword) {
        const { data } = await axios.get("/api/knowledge/entries/search", {
          params: { q: searchKeyword },
        });
        setEntries(data);
      } else {
        const { data } = await axios.get("/api/knowledge/entries", {
          params: {
            category: categoryFilter,
            defect_type: defectFilter,
            page_size: 100,
          },
        });
        setEntries(data);
      }
    } catch {
      message.error("Failed to load knowledge entries");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadEntries();
  }, [categoryFilter, defectFilter]);

  const handleSearch = () => {
    if (!searchKeyword.trim()) {
      loadEntries();
    } else {
      loadEntries();
    }
  };

  const handleCreate = async (values: Record<string, unknown>) => {
    setSubmitting(true);
    try {
      await axios.post("/api/knowledge/entries", values);
      message.success("Knowledge entry created");
      setCreateVisible(false);
      form.resetFields();
      loadEntries();
    } catch {
      message.error("Failed to create entry");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await axios.delete(`/api/knowledge/entries/${id}`);
      message.success("Entry deleted");
      loadEntries();
    } catch {
      message.error("Failed to delete entry");
    }
  };

  const handleViewDetail = (entry: KnowledgeEntry) => {
    setSelectedEntry(entry);
    setDetailVisible(true);
  };

  const handleGenerateRule = async (entry: KnowledgeEntry) => {
    try {
      const { data } = await axios.post(
        `/api/rules/generate-from-knowledge?knowledge_entry_id=${entry.knowledge_id}`
      );
      message.success(`Generated ${data.length} rule(s)`);
    } catch {
      message.error("Failed to generate rule");
    }
  };

  const categoryColorMap: Record<string, string> = {
    defect: "red",
    false_alarm: "green",
    camera_issue: "orange",
    lighting: "gold",
    process: "purple",
  };

  const columns = [
    {
      title: "Title",
      dataIndex: "title",
      key: "title",
      render: (t: string) => <Text strong>{t}</Text>,
    },
    {
      title: "Category",
      dataIndex: "category",
      key: "category",
      width: 120,
      render: (c: string) => (
        <Tag color={categoryColorMap[c] || "default"}>{c.replace(/_/g, " ")}</Tag>
      ),
    },
    {
      title: "Defect Type",
      dataIndex: "defect_type",
      key: "defect_type",
      width: 110,
      render: (d: string | null) => (
        <Tag color="purple">{d || "-"}</Tag>
      ),
    },
    {
      title: "Action",
      dataIndex: "action",
      key: "action",
      width: 80,
      render: (a: string) => {
        const colors: Record<string, string> = {
          ignore: "green",
          NG: "red",
          review_required: "orange",
        };
        return <Tag color={colors[a] || "default"}>{a}</Tag>;
      },
    },
    {
      title: "Cluster",
      dataIndex: "cluster_id",
      key: "cluster_id",
      width: 120,
      render: (c: string | null) =>
        c ? <Text code>{c.slice(0, 10)}...</Text> : <Text type="secondary">-</Text>,
    },
    {
      title: "Cameras",
      dataIndex: "camera_ids",
      key: "camera_ids",
      width: 140,
      render: (ids: string[]) =>
        ids.length > 0 ? (
          <Space size={4} wrap>
            {ids.map((id) => (
              <Tag key={id} style={{ fontSize: 11 }}>
                {id}
              </Tag>
            ))}
          </Space>
        ) : (
          <Text type="secondary">all</Text>
        ),
    },
    {
      title: "Created",
      dataIndex: "created_at",
      key: "created_at",
      width: 170,
      render: (d: string) => new Date(d).toLocaleString(),
    },
    {
      title: "Actions",
      key: "actions",
      width: 200,
      render: (_: unknown, record: KnowledgeEntry) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleViewDetail(record)}
          >
            View
          </Button>
          <Button
            type="link"
            size="small"
            icon={<BookOutlined />}
            onClick={() => handleGenerateRule(record)}
          >
            Gen Rule
          </Button>
          <Popconfirm
            title="Delete this entry?"
            onConfirm={() => handleDelete(record.knowledge_id)}
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              Delete
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <h2>Knowledge Base</h2>
        </Col>
        <Col>
          <Space>
            <Input.Search
              placeholder="Search knowledge..."
              allowClear
              style={{ width: 250 }}
              value={searchKeyword}
              onChange={(e) => setSearchKeyword(e.target.value)}
              onSearch={handleSearch}
              enterButton={<SearchOutlined />}
            />
            <Select
              placeholder="Category"
              allowClear
              style={{ width: 140 }}
              value={categoryFilter}
              onChange={(v) => {
                setCategoryFilter(v);
                setSearchKeyword("");
              }}
              options={CATEGORY_OPTIONS}
            />
            <Select
              placeholder="Defect type"
              allowClear
              style={{ width: 140 }}
              value={defectFilter}
              onChange={(v) => {
                setDefectFilter(v);
                setSearchKeyword("");
              }}
              options={DEFECT_OPTIONS}
            />
            <Button icon={<ReloadOutlined />} onClick={() => {
              setSearchKeyword("");
              setCategoryFilter(undefined);
              setDefectFilter(undefined);
            }}>
              Reset
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setCreateVisible(true)}
            >
              New Entry
            </Button>
          </Space>
        </Col>
      </Row>

      <Card>
        <Table
          columns={columns}
          dataSource={entries}
          rowKey="knowledge_id"
          loading={loading}
          pagination={{ pageSize: 20, showTotal: (t) => `Total ${t} entries` }}
          size="middle"
        />
      </Card>

      <Modal
        title="Create Knowledge Entry"
        open={createVisible}
        onCancel={() => {
          setCreateVisible(false);
          form.resetFields();
        }}
        onOk={() => form.submit()}
        confirmLoading={submitting}
        width={600}
      >
        <Form form={form} layout="vertical" onFinish={(v) => handleCreate(v)}>
          <Form.Item name="title" label="Title" rules={[{ required: true }]}>
            <Input maxLength={256} placeholder="e.g. Reflection pattern on left seat edge" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="category" label="Category" rules={[{ required: true }]}>
                <Select options={CATEGORY_OPTIONS} placeholder="Select category" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="defect_type" label="Defect Type">
                <Select options={DEFECT_OPTIONS} placeholder="Optional" allowClear />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="action" label="Action" rules={[{ required: true }]}>
            <Select options={ACTION_OPTIONS} placeholder="Select action" />
          </Form.Item>
          <Form.Item name="description" label="Description">
            <TextArea rows={3} maxLength={2000} placeholder="Describe the defect pattern..." />
          </Form.Item>
          <Form.Item name="cluster_id" label="Cluster ID">
            <Input placeholder="Optional: link to a cluster" />
          </Form.Item>
          <Form.Item name="camera_ids" label="Camera IDs (comma separated)">
            <Input placeholder="e.g. left_top, right_bottom" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="Knowledge Entry Detail"
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={
          <Space>
            {selectedEntry && (
              <>
                <Button onClick={() => handleGenerateRule(selectedEntry)}>
                  Generate Rule
                </Button>
                <Popconfirm
                  title="Delete this entry?"
                  onConfirm={() => {
                    handleDelete(selectedEntry.knowledge_id);
                    setDetailVisible(false);
                  }}
                >
                  <Button danger>Delete</Button>
                </Popconfirm>
              </>
            )}
            <Button onClick={() => setDetailVisible(false)}>Close</Button>
          </Space>
        }
        width={700}
      >
        {selectedEntry && (
          <Descriptions column={2} bordered size="small">
            <Descriptions.Item label="Title" span={2}>
              {selectedEntry.title}
            </Descriptions.Item>
            <Descriptions.Item label="Category">
              <Tag color={categoryColorMap[selectedEntry.category]}>
                {selectedEntry.category.replace(/_/g, " ")}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="Action">
              <Tag color={selectedEntry.action === "ignore" ? "green" : "red"}>
                {selectedEntry.action}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="Defect Type">
              {selectedEntry.defect_type || "-"}
            </Descriptions.Item>
            <Descriptions.Item label="Cluster">
              {selectedEntry.cluster_id || "-"}
            </Descriptions.Item>
            <Descriptions.Item label="Cameras" span={2}>
              {selectedEntry.camera_ids.length > 0
                ? selectedEntry.camera_ids.join(", ")
                : "All cameras"}
            </Descriptions.Item>
            <Descriptions.Item label="Description" span={2}>
              <Paragraph>{selectedEntry.description || "No description"}</Paragraph>
            </Descriptions.Item>
            <Descriptions.Item label="Created" span={2}>
              {new Date(selectedEntry.created_at).toLocaleString()}
            </Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </div>
  );
}
