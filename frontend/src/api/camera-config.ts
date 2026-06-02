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

interface BackendCameraConfig {
  id: string;
  camera_id: string;
  seat_model_id: string;
  efficientad_model_version_id: string | null;
  filter_classifier_model_version_id: string | null;
  normalizer_model_version_id: string | null;
  detection_confidence: number;
  efficientad_image_size: number;
  efficientad_threshold: number;
  created_at: string;
  updated_at: string;
}

interface BackendCameraConfigFormData {
  camera_id?: string;
  efficientad_model_version_id?: string | null;
  filter_classifier_model_version_id?: string | null;
  normalizer_model_version_id?: string | null;
  detection_confidence?: number;
  efficientad_image_size?: number;
  efficientad_threshold?: number;
}

function toCameraConfig(data: BackendCameraConfig): CameraConfig {
  return {
    id: data.id,
    camera_id: data.camera_id,
    seat_model_id: data.seat_model_id,
    patchcore_model_version_id: data.efficientad_model_version_id,
    filter_classifier_model_version_id: data.filter_classifier_model_version_id,
    normalizer_model_version_id: data.normalizer_model_version_id,
    detection_confidence: data.detection_confidence,
    patchcore_image_size: data.efficientad_image_size,
    patchcore_threshold: data.efficientad_threshold,
    created_at: data.created_at,
    updated_at: data.updated_at,
  };
}

function toBackendCameraPayload(
  data: Partial<CameraConfigFormData>,
): BackendCameraConfigFormData {
  const payload: BackendCameraConfigFormData = {};
  if (data.camera_id !== undefined) {
    payload.camera_id = data.camera_id;
  }
  if (data.patchcore_model_version_id !== undefined) {
    payload.efficientad_model_version_id = data.patchcore_model_version_id;
  }
  if (data.filter_classifier_model_version_id !== undefined) {
    payload.filter_classifier_model_version_id = data.filter_classifier_model_version_id;
  }
  if (data.normalizer_model_version_id !== undefined) {
    payload.normalizer_model_version_id = data.normalizer_model_version_id;
  }
  if (data.detection_confidence !== undefined) {
    payload.detection_confidence = data.detection_confidence;
  }
  if (data.patchcore_image_size !== undefined) {
    payload.efficientad_image_size = data.patchcore_image_size;
  }
  if (data.patchcore_threshold !== undefined) {
    payload.efficientad_threshold = data.patchcore_threshold;
  }
  return payload;
}

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
    get<BackendCameraConfig[]>(`/seat-models/${seatModelId}/cameras`)
      .then((items) => items.map(toCameraConfig)),

  createCamera: (seatModelId: string, data: CameraConfigFormData) =>
    post<BackendCameraConfig>(
      `/seat-models/${seatModelId}/cameras`,
      toBackendCameraPayload(data),
    ).then(toCameraConfig),

  updateCamera: (
    seatModelId: string,
    cameraDbId: string,
    data: Partial<CameraConfigFormData>,
  ) =>
    http
      .put<BackendCameraConfig>(
        `/seat-models/${seatModelId}/cameras/${cameraDbId}`,
        toBackendCameraPayload(data),
      )
      .then((res) => toCameraConfig(res.data)),

  deleteCamera: (seatModelId: string, cameraDbId: string) =>
    del(`/seat-models/${seatModelId}/cameras/${cameraDbId}`),
};
