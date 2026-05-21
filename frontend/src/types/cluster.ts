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

export interface ScatterPoint {
  cluster_id: string;
  name: string;
  x: number;
  y: number;
  sample_count: number;
  possible_type: string;
  review_status: string;
  defect_type: string;
}

export interface ClusterVizData {
  scatter_data: ScatterPoint[];
  summary: {
    total_clusters: number;
    total_samples: number;
    real_defect: number;
    false_alarm: number;
    pending_review: number;
  };
}
