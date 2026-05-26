import { get, post } from "./client";

export const maskRefinementApi = {
  refine: (anomalyId: string, signal?: AbortSignal) =>
    post(`/mask-refinement/refine/${anomalyId}`, undefined, { signal }),

  compare: (params: {
    seat_model_id?: string;
    camera_id?: string;
    region_id?: string;
  }, signal?: AbortSignal) =>
    get("/mask-refinement/compare", { params, signal }),
};
