import http from "./client";

export const efficientadTrainingApi = {
  start: (formData: FormData) =>
    http.post<{ status: string; message: string; task_id: string }>(
      "/efficientad-training/start",
      formData,
      { headers: { "Content-Type": "multipart/form-data" } },
    ).then((res) => res.data),
};
