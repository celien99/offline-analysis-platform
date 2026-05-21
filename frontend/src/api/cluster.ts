import { get, post } from "./client";
import type { ClusterListResponse, ClusterDetail, ReviewSubmit } from "../types";

export const clusterApi = {
  list: (page = 1, pageSize = 20, status?: string) =>
    get<ClusterListResponse>("/cluster/list", {
      params: { page, page_size: pageSize, status },
    }),

  detail: (clusterId: string) =>
    get<ClusterDetail>(`/cluster/${clusterId}`),

  review: (review: ReviewSubmit) =>
    post("/cluster/review", review),

  trigger: (params: {
    min_cluster_size?: number;
    min_samples?: number;
    anomaly_ids?: string[];
  }) => post("/cluster/trigger", params),

  visualization: () =>
    get("/cluster/visualization"),
};
