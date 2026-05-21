import { post } from "./client";

export const multimodalApi = {
  analyzeCluster: (clusterId: string, signal?: AbortSignal) =>
    post(`/multimodal/analyze/cluster/${clusterId}`, {}, { signal }),

  analyzeBatch: (clusterIds: string[], signal?: AbortSignal) =>
    post("/multimodal/analyze/batch", { cluster_ids: clusterIds }, { signal }),

  analyzeAnomaly: (anomalyId: string, signal?: AbortSignal) =>
    post(`/multimodal/analyze/anomaly/${anomalyId}`, {}, { signal }),
};
