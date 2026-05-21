import { get, post, del } from "./client";
import type { KnowledgeEntry } from "../types";

export const knowledgeApi = {
  list: (params: { category?: string; defect_type?: string; page_size?: number }) =>
    get<KnowledgeEntry[]>("/knowledge/entries", { params }),

  search: (q: string, limit = 20) =>
    get<KnowledgeEntry[]>("/knowledge/entries/search", { params: { q, limit } }),

  create: (entry: Record<string, unknown>) =>
    post("/knowledge/entries", entry),

  delete: (knowledgeId: string) =>
    del(`/knowledge/entries/${knowledgeId}`),
};
