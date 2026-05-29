/** POST /api/mask-refinement/refine/{id} 响应 */
export interface MaskRefineResponse {
  status: string;
  task_id: string;
  anomaly_id: string;
}

export interface TrackMetricsResult {
  embedding_type: string;
  sample_count: number;
  cluster_count: number;
  noise_count: number;
  noise_rate: number;
  avg_cluster_size: number;
  max_cluster_size: number;
  max_cluster_ratio: number;
  cluster_sizes: number[];
}

export interface DualTrackComparisonResult {
  seat_model_id: string | null;
  camera_id: string | null;
  raw: TrackMetricsResult | null;
  refined: TrackMetricsResult | null;
  recommendation: string;
  evaluated_at: string;
}
