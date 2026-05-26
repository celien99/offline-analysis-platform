import { Select } from "antd";
import type { SelectProps } from "antd";
import type { ModelOption } from "../../../types";

interface Props extends Omit<SelectProps, "options"> {
  models: ModelOption[] | undefined;
  loading?: boolean;
}

export default function ModelSelect({ models, loading, ...rest }: Props) {
  return (
    <Select
      showSearch
      optionFilterProp="label"
      loading={loading}
      placeholder="选择模型"
      allowClear
      {...rest}
      options={(models ?? []).map((m) => ({
        label: `${m.model_name} (${m.version})`,
        value: m.model_id,
      }))}
    />
  );
}
