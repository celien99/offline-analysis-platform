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
  efficientad_model_version_id: string | null;
  filter_classifier_model_version_id: string | null;
  detection_confidence: number;
  efficientad_image_size: number;
  efficientad_threshold: number;
  created_at: string;
  updated_at: string;
}

export interface CameraConfigFormData {
  camera_id: string;
  efficientad_model_version_id: string | null;
  filter_classifier_model_version_id: string | null;
  detection_confidence: number;
  efficientad_image_size: number;
  efficientad_threshold: number;
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
