export interface AnomalyRecord {
  anomaly_id: string;
  camera_id: string;
  source: string;
  anomaly_score: number | null;
  date_folder: string;
  status: string;
  detected_at: string;
  original_url: string | null;
  roi_url: string | null;
  heatmap_url: string | null;
  crop_url: string | null;
  created_at: string;
  trace_id: string | null;
}
