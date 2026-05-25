import { useState } from "react";
import { Card, Table, Button, Space, Input, Select, Form, message } from "antd";
import { PlusOutlined, ReloadOutlined, SearchOutlined } from "@ant-design/icons";
import type { KnowledgeEntry } from "../../types";
import { useKnowledgeList, useKnowledgeSearch, useKnowledgeCreate, useKnowledgeDelete } from "../../hooks/queries";
import { useRuleGenerateFromKb } from "../../hooks/queries";
import PageHeader from "../../components/ui/PageHeader";
import { useKnowledgeColumns } from "./components/KnowledgeTable";
import CreateKnowledgeForm from "./components/CreateKnowledgeForm";
import KnowledgeDetailModal from "./components/KnowledgeDetailModal";
import { CATEGORY_OPTIONS, DEFECT_TYPES } from "../../lib/constants";

export default function KnowledgeBase() {
  const [categoryFilter, setCategoryFilter] = useState<string | undefined>();
  const [defectFilter, setDefectFilter] = useState<string | undefined>();
  const [searchKeyword, setSearchKeyword] = useState("");
  const [createVisible, setCreateVisible] = useState(false);
  const [detailVisible, setDetailVisible] = useState(false);
  const [selectedEntry, setSelectedEntry] = useState<KnowledgeEntry | null>(null);
  const [form] = Form.useForm();

  const searchMode = searchKeyword.length > 0;

  const { data: listData = [], isLoading: listLoading, refetch: refetchList } = useKnowledgeList(
    { category: categoryFilter, defect_type: defectFilter },
    !searchMode,
  );
  const { data: searchData = [], isLoading: searchLoading, refetch: refetchSearch } = useKnowledgeSearch(
    searchKeyword,
    searchMode,
  );

  const entries = searchMode ? searchData : listData;
  const loading = searchMode ? searchLoading : listLoading;
  const refetch = searchMode ? refetchSearch : refetchList;

  const createMutation = useKnowledgeCreate();
  const deleteMutation = useKnowledgeDelete();
  const generateRuleMutation = useRuleGenerateFromKb();

  const handleCreate = async (values: Record<string, unknown>) => {
    try {
      await createMutation.mutateAsync(values);
      message.success("知识条目已创建");
      setCreateVisible(false);
      form.resetFields();
    } catch {
      message.error("创建条目失败");
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteMutation.mutateAsync(id);
      message.success("条目已删除");
    } catch {
      message.error("删除条目失败");
    }
  };

  const handleViewDetail = (entry: KnowledgeEntry) => {
    setSelectedEntry(entry);
    setDetailVisible(true);
  };

  const handleGenerateRule = async (entry: KnowledgeEntry) => {
    try {
      const data = await generateRuleMutation.mutateAsync(entry.knowledge_id);
      message.success(`已生成 ${(data as unknown[]).length} 条规则`);
    } catch {
      message.error("生成规则失败");
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
        title="知识库"
        extra={
          <Space>
            <Input.Search
              placeholder="搜索知识..."
              allowClear
              style={{ width: 250 }}
              value={searchKeyword}
              onChange={(e) => setSearchKeyword(e.target.value)}
              onSearch={(v) => setSearchKeyword(v)}
              enterButton={<SearchOutlined />}
            />
            <Select
              placeholder="类别"
              allowClear
              style={{ width: 140 }}
              value={categoryFilter}
              onChange={(v) => { setCategoryFilter(v); setSearchKeyword(""); }}
              options={CATEGORY_OPTIONS as { value: string; label: string }[]}
            />
            <Select
              placeholder="缺陷类型"
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
              重置
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateVisible(true)}>
              新建条目
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
          pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 条记录` }}
          size="middle"
        />
      </Card>

      <CreateKnowledgeForm
        form={form}
        open={createVisible}
        submitting={createMutation.isPending}
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
