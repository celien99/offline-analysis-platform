// frontend/src/api/camera-config.ts
import { get, post, del } from "./client";
import http from "./client";
import type {
  SeatModel,
  SeatModelOption,
  CameraConfig,
  SeatModelFormData,
  CameraConfigFormData,
} from "../types";

export const cameraConfigApi = {
  // ── Seat Models ──
  listOptions: () => get<SeatModelOption[]>("/seat-models/options"),

  listSeatModels: (params?: { page: number; page_size: number }) =>
    get<SeatModel[]>("/seat-models", { params }),

  createSeatModel: (data: SeatModelFormData) =>
    post<SeatModel>("/seat-models", data),

  updateSeatModel: (id: string, data: Partial<SeatModelFormData>) =>
    http.put<SeatModel>(`/seat-models/${id}`, data).then((res) => res.data),

  deleteSeatModel: (id: string) => del(`/seat-models/${id}`),

  // ── Camera Configs ──
  listCameras: (seatModelId: string) =>
    get<CameraConfig[]>(`/seat-models/${seatModelId}/cameras`),

  createCamera: (seatModelId: string, data: CameraConfigFormData) =>
    post<CameraConfig>(`/seat-models/${seatModelId}/cameras`, data),

  updateCamera: (
    seatModelId: string,
    cameraDbId: string,
    data: Partial<CameraConfigFormData>,
  ) =>
    http
      .put<CameraConfig>(`/seat-models/${seatModelId}/cameras/${cameraDbId}`, data)
      .then((res) => res.data),

  deleteCamera: (seatModelId: string, cameraDbId: string) =>
    del(`/seat-models/${seatModelId}/cameras/${cameraDbId}`),
};
