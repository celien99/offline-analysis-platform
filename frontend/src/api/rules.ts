import { get, post, del } from "./client";
import type { Rule, EvalResult, PaginatedResponse } from "../types";

export const rulesApi = {
  list: (params: { rule_type?: string; page_size?: number }, signal?: AbortSignal) =>
    get<PaginatedResponse<Rule>>("/rules", { params, signal }),

  create: (params: Record<string, unknown>, signal?: AbortSignal) =>
    post("/rules", null, { params, signal }),

  evaluate: (params: {
    camera_id: string;
    defect_type?: string;
    anomaly_score?: number;
    classifier_prediction?: string;
  }, signal?: AbortSignal) => post<EvalResult>("/rules/evaluate", null, { params, signal }),

  toggle: (ruleId: string, enabled: boolean, signal?: AbortSignal) =>
    post(`/rules/${ruleId}/toggle?enabled=${enabled}`, undefined, { signal }),

  delete: (ruleId: string, signal?: AbortSignal) =>
    del(`/rules/${ruleId}`, { signal }),

  generateFromKnowledge: (knowledgeEntryId: string, signal?: AbortSignal) =>
    post(`/rules/generate-from-knowledge?knowledge_entry_id=${knowledgeEntryId}`, undefined, { signal }),
};
