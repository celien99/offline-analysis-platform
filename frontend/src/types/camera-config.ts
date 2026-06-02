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
  yolo_model_version_id: string | null;
  projector_model_version_id: string | null;
  whitening_matrix_model_version_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface CameraConfig {
  id: string;
  camera_id: string;
  seat_model_id: string;
  patchcore_model_version_id: string | null;
  filter_classifier_model_version_id: string | null;
  normalizer_model_version_id: string | null;
  detection_confidence: number;
  patchcore_image_size: number;
  patchcore_threshold: number;
  regions: CameraRegionConfig[];
  created_at: string;
  updated_at: string;
}

export interface CameraRegionConfig {
  id?: string;
  region_id: string;
  box?: [number, number, number, number] | null;
  patchcore_model_version_id: string | null;
  enabled?: boolean;
  sort_order?: number;
  patchcore?: Record<string, object | undefined> | null;
}

export interface CameraConfigFormData {
  camera_id: string;
  patchcore_model_version_id: string | null;
  filter_classifier_model_version_id: string | null;
  normalizer_model_version_id: string | null;
  detection_confidence: number;
  patchcore_image_size: number;
  patchcore_threshold: number;
  regions: CameraRegionConfig[];
}

export interface SeatModelFormData {
  seat_model_id: string;
  display_name: string;
  yolo_model_version_id: string | null;
  projector_model_version_id: string | null;
  whitening_matrix_model_version_id: string | null;
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
