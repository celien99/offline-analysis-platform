import { get, post, del } from "./client";
import type { Rule, EvalResult } from "../types";

export const rulesApi = {
  list: (params: { rule_type?: string; page_size?: number }) =>
    get<Rule[]>("/rules", { params }),

  create: (params: Record<string, unknown>) =>
    post("/rules", null, { params }),

  evaluate: (params: {
    camera_id: string;
    defect_type?: string;
    anomaly_score?: number;
    classifier_prediction?: string;
  }) => post<EvalResult>("/rules/evaluate", null, { params }),

  toggle: (ruleId: string, enabled: boolean) =>
    post(`/rules/${ruleId}/toggle?enabled=${enabled}`),

  delete: (ruleId: string) =>
    del(`/rules/${ruleId}`),

  generateFromKnowledge: (knowledgeEntryId: string) =>
    post(`/rules/generate-from-knowledge?knowledge_entry_id=${knowledgeEntryId}`),
};
