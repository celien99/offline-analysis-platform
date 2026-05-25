import { Modal, Select, Input, Typography } from "antd";
import type { ClusterDetail } from "../../../types";
import { DEFECT_TYPES } from "../../../lib/constants";

const { TextArea } = Input;
const { Text } = Typography;

interface Props {
  cluster: ClusterDetail | null;
  action: "confirm_defect" | "mark_false_alarm";
  defectType: string | undefined;
  comment: string;
  submitting: boolean;
  open: boolean;
  onDefectTypeChange: (v: string | undefined) => void;
  onCommentChange: (v: string) => void;
  onSubmit: () => void;
  onClose: () => void;
}

export default function ReviewModal({
  action,
  defectType,
  comment,
  submitting,
  open,
  onDefectTypeChange,
  onCommentChange,
  onSubmit,
  onClose,
}: Props) {
  return (
    <Modal
      title={action === "confirm_defect" ? "确认为真实缺陷" : "标记为误报"}
      open={open}
      onOk={onSubmit}
      onCancel={onClose}
      confirmLoading={submitting}
    >
      {action === "confirm_defect" && (
        <div className="mb-4">
          <Text strong>缺陷类型:</Text>
          <Select
            className="w-full mt-2"
            placeholder="选择缺陷类型"
            options={DEFECT_TYPES as unknown as { value: string; label: string }[]}
            value={defectType}
            onChange={onDefectTypeChange}
            allowClear
          />
        </div>
      )}
      <div>
        <Text strong>备注:</Text>
        <TextArea
          className="mt-2"
          rows={3}
          placeholder="可选备注信息..."
          value={comment}
          onChange={(e) => onCommentChange(e.target.value)}
        />
      </div>
    </Modal>
  );
}
