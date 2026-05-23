import http from "./client";

export const referenceApi = {
  upload: (cameraId: string, file: File) => {
    const formData = new FormData();
    formData.append("camera_id", cameraId);
    formData.append("image_file", file);
    return http.post("/reference/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },

  list: (signal?: AbortSignal) =>
    http.get<{ camera_id: string }[]>("/reference/list", { signal }),

  getUrl: (cameraId: string, signal?: AbortSignal) =>
    http.get<{ camera_id: string; url: string | null }>(
      `/reference/${cameraId}`,
      { signal },
    ),
};
