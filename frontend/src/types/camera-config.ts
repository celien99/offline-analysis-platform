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
  patchcore_model_path: string;
  yolo_model_path: string;
  detection_confidence: number;
  patchcore_image_size: number;
  patchcore_threshold: number;
  region_mode_enabled: boolean;
  region_upper_model_path: string | null;
  region_middle_model_path: string | null;
  region_lower_model_path: string | null;
  created_at: string;
  updated_at: string;
}

export interface CameraConfigFormData {
  camera_id: string;
  patchcore_model_path: string;
  yolo_model_path: string;
  detection_confidence: number;
  patchcore_image_size: number;
  patchcore_threshold: number;
  region_mode_enabled: boolean;
  region_upper_model_path: string;
  region_middle_model_path: string;
  region_lower_model_path: string;
}

export interface SeatModelFormData {
  seat_model_id: string;
  display_name: string;
}
