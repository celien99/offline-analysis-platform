import { get } from "./client";
import http from "./client";
import type { InspectionResult } from "../types";

export const inspectionApi = {
  run: (formData: FormData) =>
    http.post<{ status: string; message: string; task_id: string }>(
      "/inspection/run-with-files",
      formData,
      { headers: { "Content-Type": "multipart/form-data" } },
    ).then((res) => res.data),

  result: (taskId: string, signal?: AbortSignal) =>
    get<InspectionResult>(`/inspection/result/${taskId}`, { signal }),
};
