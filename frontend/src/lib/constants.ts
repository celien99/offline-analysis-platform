export const DEFECT_TYPES = [
  { value: "wrinkle", label: "褶皱" },
  { value: "scratch", label: "划痕" },
  { value: "reflection", label: "反光" },
  { value: "stain", label: "污渍" },
  { value: "seam_shift", label: "接缝偏移" },
];

export const CATEGORY_OPTIONS = [
  { value: "defect", label: "缺陷" },
  { value: "false_alarm", label: "误报" },
  { value: "camera_issue", label: "相机问题" },
  { value: "lighting", label: "光照问题" },
  { value: "process", label: "工艺问题" },
];

export const ACTION_OPTIONS = [
  { value: "ignore", label: "忽略" },
  { value: "NG", label: "NG" },
  { value: "review_required", label: "需人工复核" },
];

export const RULE_TYPE_OPTIONS = [
  { value: "ignore", label: "忽略" },
  { value: "flag", label: "标记" },
  { value: "escalate", label: "升级" },
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
