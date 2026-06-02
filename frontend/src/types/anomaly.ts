export interface AnomalyRecord {
  anomaly_id: string;
  camera_id: string;
  seat_model_id: string | null;
  region_id: string | null;
  source: string;
  anomaly_score: number | null;
  date_folder: string;
  status: string;
  detected_at: string;
  original_url: string | null;
  heatmap_url: string | null;
  crop_url: string | null;
  crop_urls: string[];
  cluster_id: string | null;
  created_at: string;
  trace_id: string | null;
}

/** 轻量 anomaly 摘要，用于 cluster 详情页列表展示。 */
export interface AnomalySummary {
  anomaly_id: string;
  camera_id: string;
  seat_model_id?: string | null;
  region_id?: string | null;
  anomaly_score: number | null;
  status: string;
  crop_url: string | null;
  detected_at: string | null;
}

/** POST /api/anomaly/{id}/reprocess 响应 */
export interface AnomalyReprocessResponse {
  status: string;
  anomaly_id: string;
}

/** DELETE /api/anomaly/{id} 响应 */
export interface AnomalyDeleteResponse {
  status: string;
  anomaly_id: string;
}

/** GET /api/embedding/search 响应 - 相似 embedding 搜索结果 */
export interface EmbeddingSimilarResult {
  anomaly_id: string;
  similarity: number;
  seat_model_id?: string | null;
  camera_id?: string | null;
  region_id?: string | null;
  date_folder?: string | null;
  crop_url?: string | null;
}
