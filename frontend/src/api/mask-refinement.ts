import { get, post } from "./client";
import type { MaskRefineResponse, DualTrackComparisonResult } from "../types";

export const maskRefinementApi = {
  refine: (anomalyId: string, signal?: AbortSignal) =>
    post<MaskRefineResponse>(`/mask-refinement/refine/${anomalyId}`, undefined, { signal }),

  compare: (params: {
    seat_model_id?: string;
    camera_id?: string;
  }, signal?: AbortSignal) =>
    get<DualTrackComparisonResult>("/mask-refinement/compare", { params, signal }),
};
