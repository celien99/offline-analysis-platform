import { post } from "./client";
import type { VLMAnalysisResponse, VLMBatchAnalysisResponse, VLMAnomalyAnalysisResponse } from "../types";

export const multimodalApi = {
  analyzeCluster: (clusterId: string, signal?: AbortSignal) =>
    post<VLMAnalysisResponse>(`/multimodal/analyze/cluster/${clusterId}`, {}, { signal }),

  analyzeBatch: (clusterIds: string[], signal?: AbortSignal) =>
    post<VLMBatchAnalysisResponse>("/multimodal/analyze/batch", { cluster_ids: clusterIds }, { signal }),

  analyzeAnomaly: (anomalyId: string, signal?: AbortSignal) =>
    post<VLMAnomalyAnalysisResponse>(`/multimodal/analyze/anomaly/${anomalyId}`, {}, { signal }),
};
