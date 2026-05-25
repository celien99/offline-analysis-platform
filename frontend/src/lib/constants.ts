export const DEFECT_TYPES = [
  { value: "wrinkle", label: "Wrinkle" },
  { value: "scratch", label: "Scratch" },
  { value: "reflection", label: "Reflection" },
  { value: "stain", label: "Stain" },
  { value: "seam_shift", label: "Seam Shift" },
];

export const CATEGORY_OPTIONS = [
  { value: "defect", label: "Defect" },
  { value: "false_alarm", label: "False Alarm" },
  { value: "camera_issue", label: "Camera Issue" },
  { value: "lighting", label: "Lighting" },
  { value: "process", label: "Process" },
];

export const ACTION_OPTIONS = [
  { value: "ignore", label: "Ignore" },
  { value: "NG", label: "NG" },
  { value: "review_required", label: "Review Required" },
];

export const RULE_TYPE_OPTIONS = [
  { value: "ignore", label: "Ignore" },
  { value: "flag", label: "Flag" },
  { value: "escalate", label: "Escalate" },
];

export const STATUS_COLORS: Record<string, string> = {
  real_defect: "#ff4d4f",
  false_alarm: "#52c41a",
  pending_review: "#faad14",
};

export const STATUS_COLOR_MAP: Record<string, string> = {
  real_defect: "red",
  false_alarm: "green",
};

export const ANOMALY_STATUS_COLOR_MAP: Record<string, string> = {
  pending: "orange",
  embedded: "blue",
  noise: "volcano",
  clustered: "cyan",
  reviewed: "green",
};

export const CATEGORY_COLOR_MAP: Record<string, string> = {
  defect: "red",
  false_alarm: "green",
  camera_issue: "orange",
  lighting: "gold",
  process: "purple",
};

export const RULE_TYPE_COLOR_MAP: Record<string, string> = {
  ignore: "green",
  flag: "orange",
  escalate: "red",
};
