import { get, post } from "./client";
import type { ClusterListResponse, ClusterDetail, ClusterVizData, ReviewSubmit } from "../types";

export const clusterApi = {
  list: (page = 1, pageSize = 20, status?: string, signal?: AbortSignal) =>
    get<ClusterListResponse>("/cluster/list", {
      params: { page, page_size: pageSize, status },
      signal,
    }),

  detail: (clusterId: string, signal?: AbortSignal) =>
    get<ClusterDetail>(`/cluster/${clusterId}`, { signal }),

  review: (review: ReviewSubmit, signal?: AbortSignal) =>
    post("/cluster/review", review, { signal }),

  trigger: (params: {
    min_cluster_size?: number;
    min_samples?: number;
    anomaly_ids?: string[];
  }, signal?: AbortSignal) => post("/cluster/trigger", params, { signal }),

  visualization: (signal?: AbortSignal) =>
    get<ClusterVizData>("/cluster/visualization", { signal }),
};
