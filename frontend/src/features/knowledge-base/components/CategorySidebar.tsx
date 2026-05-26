import { Tree } from "antd";
import type { DataNode } from "antd/es/tree";
import { CATEGORY_OPTIONS, DEFECT_TYPES } from "../../../lib/constants";

const treeData: DataNode[] = [
  { title: "全部", key: "all" },
  ...CATEGORY_OPTIONS.map((c) => ({ title: c.label, key: c.value })),
];

interface Props {
  selectedCategory: string | null;
  onSelect: (key: string | null) => void;
}

export default function CategorySidebar({ selectedCategory, onSelect }: Props) {
  return (
    <div className="bg-white rounded-card p-4 shadow-card-sm">
      <div className="text-sm font-semibold text-gray-500 mb-3">类别</div>
      <Tree
        treeData={treeData}
        selectedKeys={selectedCategory ? [selectedCategory] : ["all"]}
        onSelect={(keys) => {
          const key = keys[0] as string;
          onSelect(key === "all" ? null : key);
        }}
        defaultExpandAll
        blockNode
        className="text-sm"
      />
      <div className="text-sm font-semibold text-gray-500 mt-4 mb-3">缺陷类型</div>
      <div className="flex flex-wrap gap-1">
        {DEFECT_TYPES.map((d) => (
          <button
            key={d.value}
            onClick={() => onSelect(d.value)}
            className="px-2 py-1 text-xs rounded border border-gray-200 hover:border-primary hover:text-primary transition-colors"
            style={{
              borderColor: selectedCategory === d.value ? "var(--color-primary)" : undefined,
              color: selectedCategory === d.value ? "var(--color-primary)" : undefined,
            }}
          >
            {d.label}
          </button>
        ))}
      </div>
    </div>
  );
}
