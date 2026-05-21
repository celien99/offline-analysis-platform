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

export interface ClusterSummary {
  cluster_id: string;
  name: string | null;
  sample_count: number;
  possible_type: string | null;
  hdbscan_label: number;
  hdbscan_probability: number | null;
  umap_x: number | null;
  umap_y: number | null;
  status: string;
  review_status: string | null;
  defect_type: string | null;
  representative_image_urls: string[];
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string;
}

export interface ClusterDetail {
  cluster_id: string;
  name: string | null;
  sample_count: number;
  possible_type: string | null;
  hdbscan_label: number;
  hdbscan_probability: number | null;
  umap_x: number | null;
  umap_y: number | null;
  status: string;
  review_status: string | null;
  defect_type: string | null;
  representative_ids: string[];
  representative_image_urls: string[];
  centroid: number[] | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  clustering_run_at: string;
  created_at: string;
}

export interface ClusterListResponse {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  clusters: ClusterSummary[];
}

export interface ReviewSubmit {
  cluster_id: string;
  reviewer: string;
  action: "confirm_defect" | "mark_false_alarm" | "rename" | "split" | "merge" | "ignore";
  defect_type?: "wrinkle" | "scratch" | "reflection" | "stain" | "seam_shift";
  comment?: string;
  new_cluster_name?: string;
}

export interface PaginatedParams {
  page: number;
  page_size: number;
}
