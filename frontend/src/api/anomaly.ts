import { del, get, post } from "./client";
import type { AnomalyRecord, AnomalyReprocessResponse, AnomalyDeleteResponse, EmbeddingSimilarResult, PaginatedResponse } from "../types";

export const anomalyApi = {
  list: (params: {
    camera_id?: string;
    seat_model_id?: string;
    region_id?: string;
    source?: string;
    status?: string;
    page?: number;
    page_size?: number;
  }, signal?: AbortSignal) =>
    get<PaginatedResponse<AnomalyRecord>>("/anomaly/list", { params, signal }),

  detail: (anomalyId: string, signal?: AbortSignal) =>
    get<AnomalyRecord>(`/anomaly/${anomalyId}`, { signal }),

  reprocess: (anomalyId: string, signal?: AbortSignal) =>
    post<AnomalyReprocessResponse>(`/anomaly/${anomalyId}/reprocess`, undefined, { signal }),

  delete: (anomalyId: string) =>
    del<AnomalyDeleteResponse>(`/anomaly/${anomalyId}`),

  searchSimilar: (anomalyId: string, topK = 20, threshold = 0.7, signal?: AbortSignal) =>
    get<EmbeddingSimilarResult[]>("/embedding/search", {
      params: { anomaly_id: anomalyId, top_k: topK, threshold },
      signal,
    }),


};
