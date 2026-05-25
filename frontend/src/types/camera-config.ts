// frontend/src/types/camera-config.ts
export interface CameraOption {
  camera_id: string;
}

export interface SeatModelOption {
  seat_model_id: string;
  display_name: string;
  cameras: CameraOption[];
}

export interface SeatModel {
  id: string;
  seat_model_id: string;
  display_name: string;
  created_at: string;
  updated_at: string;
}

export interface CameraConfig {
  id: string;
  camera_id: string;
  seat_model_id: string;
  patchcore_model_version_id: string | null;
  yolo_model_version_id: string | null;
  filter_classifier_model_version_id: string | null;
  detection_confidence: number;
  patchcore_image_size: number;
  patchcore_threshold: number;
  region_mode_enabled: boolean;
  region_upper_model_version_id: string | null;
  region_middle_model_version_id: string | null;
  region_lower_model_version_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface CameraConfigFormData {
  camera_id: string;
  patchcore_model_version_id: string | null;
  yolo_model_version_id: string | null;
  filter_classifier_model_version_id: string | null;
  detection_confidence: number;
  patchcore_image_size: number;
  patchcore_threshold: number;
  region_mode_enabled: boolean;
  region_upper_model_version_id: string | null;
  region_middle_model_version_id: string | null;
  region_lower_model_version_id: string | null;
}

export interface SeatModelFormData {
  seat_model_id: string;
  display_name: string;
}

/** 模型选项（下拉框用） */
export interface ModelOption {
  model_id: string;
  model_name: string;
  version: string;
  model_type: string;
  artifact_path: string;
}

/** 注册外部模型 */
export interface ModelRegisterData {
  model_name: string;
  version: string;
  model_type: string;
  artifact_path: string;
}
