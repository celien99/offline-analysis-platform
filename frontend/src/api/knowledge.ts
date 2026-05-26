import { get, post, del } from "./client";
import type { KnowledgeEntry, KnowledgeCreateResponse, PaginatedResponse } from "../types";

export const knowledgeApi = {
  list: (params: { category?: string; defect_type?: string; page_size?: number }, signal?: AbortSignal) =>
    get<PaginatedResponse<KnowledgeEntry>>("/knowledge/entries", { params, signal }),

  search: (q: string, limit = 20, signal?: AbortSignal) =>
    get<KnowledgeEntry[]>("/knowledge/entries/search", { params: { q, limit }, signal }),

  create: (entry: Record<string, unknown>, signal?: AbortSignal) =>
    post<KnowledgeCreateResponse>("/knowledge/entries", entry, { signal }),

  delete: (knowledgeId: string, signal?: AbortSignal) =>
    del(`/knowledge/entries/${knowledgeId}`, { signal }),
};
