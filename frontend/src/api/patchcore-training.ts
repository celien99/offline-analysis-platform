import http from "./client";

export const patchcoreTrainingApi = {
  start: (formData: FormData) =>
    http.post<{ status: string; message: string; task_id: string }>(
      "/patchcore-training/start",
      formData,
      { headers: { "Content-Type": "multipart/form-data" } },
    ).then((res) => res.data),
};
