import { useEffect, useState } from "react";
import { Card, Table, Button, Space, Input, Select, Form, message } from "antd";
import { PlusOutlined, ReloadOutlined, SearchOutlined } from "@ant-design/icons";
import type { KnowledgeEntry } from "../../types";
import { knowledgeApi, rulesApi } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import { useKnowledgeColumns } from "./components/KnowledgeTable";
import CreateKnowledgeForm from "./components/CreateKnowledgeForm";
import KnowledgeDetailModal from "./components/KnowledgeDetailModal";
import { CATEGORY_OPTIONS, DEFECT_TYPES } from "../../lib/constants";

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

  const load = async () => {
    setLoading(true);
    try {
      setEntries(
        searchKeyword
          ? await knowledgeApi.search(searchKeyword)
          : await knowledgeApi.list({ category: categoryFilter, defect_type: defectFilter, page_size: 100 }),
      );
    } catch {
      message.error("Failed to load knowledge entries");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [categoryFilter, defectFilter]);

  const handleSearch = () => load();

  const handleCreate = async (values: Record<string, unknown>) => {
    setSubmitting(true);
    try {
      await knowledgeApi.create(values);
      message.success("Knowledge entry created");
      setCreateVisible(false);
      form.resetFields();
      load();
    } catch {
      message.error("Failed to create entry");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await knowledgeApi.delete(id);
      message.success("Entry deleted");
      load();
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
      const data = await rulesApi.generateFromKnowledge(entry.knowledge_id);
      message.success(`Generated ${(data as unknown[]).length} rule(s)`);
    } catch {
      message.error("Failed to generate rule");
    }
  };

  const columns = useKnowledgeColumns({
    onViewDetail: handleViewDetail,
    onGenerateRule: handleGenerateRule,
    onDelete: handleDelete,
  });

  return (
    <div>
      <PageHeader
        title="Knowledge Base"
        extra={
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
              onChange={(v) => { setCategoryFilter(v); setSearchKeyword(""); }}
              options={CATEGORY_OPTIONS as { value: string; label: string }[]}
            />
            <Select
              placeholder="Defect type"
              allowClear
              style={{ width: 140 }}
              value={defectFilter}
              onChange={(v) => { setDefectFilter(v); setSearchKeyword(""); }}
              options={DEFECT_TYPES as { value: string; label: string }[]}
            />
            <Button
              icon={<ReloadOutlined />}
              onClick={() => { setSearchKeyword(""); setCategoryFilter(undefined); setDefectFilter(undefined); }}
            >
              Reset
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateVisible(true)}>
              New Entry
            </Button>
          </Space>
        }
      />

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

      <CreateKnowledgeForm
        form={form}
        open={createVisible}
        submitting={submitting}
        onSubmit={handleCreate}
        onClose={() => { setCreateVisible(false); form.resetFields(); }}
      />

      <KnowledgeDetailModal
        entry={selectedEntry}
        open={detailVisible}
        onClose={() => setDetailVisible(false)}
        onGenerateRule={handleGenerateRule}
        onDelete={handleDelete}
      />
    </div>
  );
}
