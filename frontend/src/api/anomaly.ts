import { get, post } from "./client";
import type { AnomalyRecord } from "../types";

export const anomalyApi = {
  list: (params: {
    camera_id?: string;
    source?: string;
    status?: string;
    page?: number;
    page_size?: number;
  }, signal?: AbortSignal) =>
    get<AnomalyRecord[]>("/anomaly/list", { params, signal }),

  detail: (anomalyId: string, signal?: AbortSignal) =>
    get<AnomalyRecord>(`/anomaly/${anomalyId}`, { signal }),

  reprocess: (anomalyId: string, signal?: AbortSignal) =>
    post(`/anomaly/${anomalyId}/reprocess`, undefined, { signal }),

  searchSimilar: (anomalyId: string, topK = 20, threshold = 0.7, signal?: AbortSignal) =>
    get("/embedding/search", {
      params: { anomaly_id: anomalyId, top_k: topK, threshold },
      signal,
    }),
};
