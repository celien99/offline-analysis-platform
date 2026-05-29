import { Button, Select, Input, Space, Radio } from "antd";
import { PlusOutlined, DeleteOutlined } from "@ant-design/icons";

interface Condition {
  field: string;
  operator: string;
  value: string;
}

interface Props {
  value?: Condition[];
  onChange?: (conditions: Condition[]) => void;
}

const FIELD_OPTIONS = [
  { value: "camera_id", label: "相机ID" },
  { value: "defect_type", label: "缺陷类型" },
  { value: "anomaly_score", label: "异常分数" },
  { value: "classifier_prediction", label: "分类器预测" },
];

const OPERATOR_OPTIONS: Record<string, { value: string; label: string }[]> = {
  default: [
    { value: "=", label: "等于" },
    { value: "!=", label: "不等于" },
  ],
  anomaly_score: [
    { value: ">", label: "大于" },
    { value: "<", label: "小于" },
    { value: ">=", label: "大于等于" },
    { value: "<=", label: "小于等于" },
    { value: "=", label: "等于" },
  ],
};

export default function RuleConditionBuilder({ value, onChange }: Props) {
  const conditions = value ?? [];

  const addCondition = () => {
    onChange?.([...conditions, { field: "camera_id", operator: "=", value: "" }]);
  };

  const removeCondition = (index: number) => {
    onChange?.(conditions.filter((_, i) => i !== index));
  };

  const updateCondition = (index: number, updates: Partial<Condition>) => {
    onChange?.(conditions.map((c, i) => (i === index ? { ...c, ...updates } : c)));
  };

  return (
    <div className="border border-gray-200 rounded-card p-4 bg-gray-50">
      {conditions.map((cond, i) => (
        <div key={i}>
          {i > 0 && (
            <div className="flex items-center gap-2 mb-2 ml-2">
              <Radio.Group
                value="AND"
                size="small"
                options={[
                  { value: "AND", label: "且" },
                  { value: "OR", label: "或" },
                ]}
                optionType="button"
                buttonStyle="solid"
              />
              <span className="text-xs text-gray-400">条件 {i + 1}</span>
            </div>
          )}
          <Space className="mb-2 w-full" size="small">
            <Select
              value={cond.field}
              onChange={(v) => updateCondition(i, { field: v, operator: "=" })}
              options={FIELD_OPTIONS}
              className="w-[140px]"
              size="small"
            />
            <Select
              value={cond.operator}
              onChange={(v) => updateCondition(i, { operator: v })}
              options={OPERATOR_OPTIONS[cond.field] || OPERATOR_OPTIONS.default}
              className="w-[100px]"
              size="small"
            />
            <Input
              value={cond.value}
              onChange={(e) => updateCondition(i, { value: e.target.value })}
              placeholder="值"
              className="w-[200px]"
              size="small"
            />
            {conditions.length > 1 && (
              <Button
                size="small"
                danger
                type="text"
                icon={<DeleteOutlined />}
                onClick={() => removeCondition(i)}
              />
            )}
          </Space>
        </div>
      ))}
      <Button size="small" type="dashed" icon={<PlusOutlined />} onClick={addCondition} block>
        添加条件
      </Button>
    </div>
  );
}
