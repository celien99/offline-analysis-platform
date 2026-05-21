import { get, post } from "./client";
import type { AnomalyRecord } from "../types";

export const anomalyApi = {
  list: (params: {
    camera_id?: string;
    source?: string;
    status?: string;
    page?: number;
    page_size?: number;
  }) => get<AnomalyRecord[]>("/anomaly/list", { params }),

  detail: (anomalyId: string) =>
    get<AnomalyRecord>(`/anomaly/${anomalyId}`),

  reprocess: (anomalyId: string) =>
    post(`/anomaly/${anomalyId}/reprocess`),

  searchSimilar: (anomalyId: string, topK = 20, threshold = 0.7) =>
    get("/embedding/search", {
      params: { anomaly_id: anomalyId, top_k: topK, threshold },
    }),
};
