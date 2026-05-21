export interface ApiError {
  code: string;
  message: string;
  detail?: string;
}

export interface PaginatedParams {
  page?: number;
  page_size?: number;
}

export interface PaginatedResponse<T> {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  items: T[];
}

export interface ReviewSubmit {
  cluster_id: string;
  reviewer: string;
  action: "confirm_defect" | "mark_false_alarm" | "rename" | "split" | "merge" | "ignore";
  defect_type?: "wrinkle" | "scratch" | "reflection" | "stain" | "seam_shift";
  comment?: string;
  new_cluster_name?: string;
  merge_source_ids?: string[];
  split_member_ids?: string[];
}
