import { get, post } from "./client";
import http from "./client";
import type { AnomalyRecord, PaginatedResponse } from "../types";

export const anomalyApi = {
  list: (params: {
    camera_id?: string;
    source?: string;
    status?: string;
    page?: number;
    page_size?: number;
  }, signal?: AbortSignal) =>
    get<PaginatedResponse<AnomalyRecord>>("/anomaly/list", { params, signal }),

  detail: (anomalyId: string, signal?: AbortSignal) =>
    get<AnomalyRecord>(`/anomaly/${anomalyId}`, { signal }),

  reprocess: (anomalyId: string, signal?: AbortSignal) =>
    post(`/anomaly/${anomalyId}/reprocess`, undefined, { signal }),

  searchSimilar: (anomalyId: string, topK = 20, threshold = 0.7, signal?: AbortSignal) =>
    get("/embedding/search", {
      params: { anomaly_id: anomalyId, top_k: topK, threshold },
      signal,
    }),

  upload: (params: {
    camera_id: string;
    source?: string;
    anomaly_score?: number;
    date_folder: string;
    detected_at: string;
    metadata?: Record<string, unknown>;
  }, signal?: AbortSignal) =>
    post<{ anomaly_id: string; status: string }>("/anomaly/upload", params, { signal }),

  uploadWithFiles: (formData: FormData) =>
    http.post<{ anomaly_id: string; status: string }>(
      "/anomaly/upload-with-files",
      formData,
      { headers: { "Content-Type": "multipart/form-data" } },
    ).then((res) => res.data),
};
