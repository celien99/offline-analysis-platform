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
  cluster_id: string | null;
  created_at: string;
  trace_id: string | null;
}

/** 轻量 anomaly 摘要，用于 cluster 详情页列表展示。 */
export interface AnomalySummary {
  anomaly_id: string;
  camera_id: string;
  anomaly_score: number | null;
  status: string;
  crop_url: string | null;
  detected_at: string | null;
}
