export interface CameraInspectionResult {
  camera_id: string;
  status: string;
  anomaly_score: number | null;
  threshold: number | null;
  is_anomaly: boolean | null;
  decision_reason: string | null;
  error_message: string | null;
  overlay_image_base64: string | null;
}

export interface InspectionResult {
  task_id: string;
  status: string;
  overall_status: string | null;
  decision_reason: string | null;
  camera_results: CameraInspectionResult[];
  error_message: string | null;
  created_at?: string;
}
