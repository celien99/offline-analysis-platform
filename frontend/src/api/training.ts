import { get, post } from "./client";
import type { TrainingStartParams, TrainingStatus, TrainedModelList } from "../types";

export const trainingApi = {
  start: (params: TrainingStartParams, signal?: AbortSignal) =>
    post<TrainingStatus>("/training/start", params, { signal }),

  status: (taskId: string, signal?: AbortSignal) =>
    get<TrainingStatus>(`/training/status/${taskId}`, { signal }),

  listModels: (params: {
    model_type?: string;
    page?: number;
    page_size?: number;
  }, signal?: AbortSignal) =>
    get<TrainedModelList>("/training/models", { params, signal }),
};
