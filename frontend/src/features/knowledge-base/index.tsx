import { useState } from "react";
import { Row, Col, Space, Input, Button, Form, message, Empty } from "antd";
import { PlusOutlined, SearchOutlined } from "@ant-design/icons";
import type { KnowledgeEntry } from "../../types";
import { useKnowledgeList, useKnowledgeSearch, useKnowledgeCreate, useKnowledgeDelete } from "../../hooks/queries";
import { useRuleGenerateFromKb } from "../../hooks/queries";
import PageHeader from "../../components/ui/PageHeader";
import CategorySidebar from "./components/CategorySidebar";
import KnowledgeCard from "./components/KnowledgeCard";
import CreateKnowledgeForm from "./components/CreateKnowledgeForm";
import KnowledgeDetailModal from "./components/KnowledgeDetailModal";
import { CardGridSkeleton } from "../../components/ui/StateSkeleton";

export default function KnowledgeBase() {
  const [categoryFilter, setCategoryFilter] = useState<string | undefined>();
  const [searchKeyword, setSearchKeyword] = useState("");
  const [createVisible, setCreateVisible] = useState(false);
  const [detailVisible, setDetailVisible] = useState(false);
  const [selectedEntry, setSelectedEntry] = useState<KnowledgeEntry | null>(null);
  const [form] = Form.useForm();

  const searchMode = searchKeyword.length > 0;

  const { data: listData = [], isLoading: listLoading } = useKnowledgeList(
    { category: categoryFilter },
    !searchMode,
  );
  const { data: searchData = [], isLoading: searchLoading } = useKnowledgeSearch(
    searchKeyword,
    searchMode,
  );

  const entries = searchMode ? searchData : listData;
  const loading = searchMode ? searchLoading : listLoading;

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
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateVisible(true)}>
              新建条目
            </Button>
          </Space>
        }
      />

      <Row gutter={16}>
        <Col xs={24} md={6}>
          <CategorySidebar
            selectedCategory={categoryFilter ?? null}
            onSelect={(key) => setCategoryFilter(key ?? undefined)}
          />
        </Col>
        <Col xs={24} md={18}>
          {loading ? (
            <CardGridSkeleton count={6} />
          ) : entries.length === 0 ? (
            <div className="bg-white rounded-card p-16 flex justify-center">
              <Empty description="暂无知识条目" />
            </div>
          ) : (
            <div className="grid gap-4" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))" }}>
              {entries.map((entry) => (
                <KnowledgeCard
                  key={entry.knowledge_id}
                  entry={entry}
                  onViewDetail={handleViewDetail}
                  onGenerateRule={handleGenerateRule}
                  onDelete={handleDelete}
                />
              ))}
            </div>
          )}
        </Col>
      </Row>

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
