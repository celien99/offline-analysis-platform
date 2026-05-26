import { get, post } from "./client";
import type { GateEvaluationReport, GateStatus } from "../types";

export const gateApi = {
  status: (modelVersionId: string, signal?: AbortSignal) =>
    get<GateStatus>(`/gates/status/${modelVersionId}`, { signal }),

  report: (modelVersionId: string, signal?: AbortSignal) =>
    get<GateEvaluationReport>(`/gates/report/${modelVersionId}`, { signal }),

  evaluate: (modelVersionId: string) =>
    post("/gates/evaluate", { model_version_id: modelVersionId }),
};
