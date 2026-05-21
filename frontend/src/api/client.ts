import axios from "axios";
import type {
  AnomalyRecord,
  ClusterListResponse,
  ClusterDetail,
  ReviewSubmit,
} from "../types";

const api = axios.create({
  baseURL: "/api",
  timeout: 30000,
});

// ── Cluster ──

export async function fetchClusters(
  page = 1,
  pageSize = 20,
  status?: string
): Promise<ClusterListResponse> {
  const { data } = await api.get<ClusterListResponse>("/cluster/list", {
    params: { page, page_size: pageSize, status },
  });
  return data;
}

export async function fetchClusterDetail(
  clusterId: string
): Promise<ClusterDetail> {
  const { data } = await api.get<ClusterDetail>(`/cluster/${clusterId}`);
  return data;
}

export async function submitReview(review: ReviewSubmit): Promise<unknown> {
  const { data } = await api.post("/cluster/review", review);
  return data;
}

export async function triggerClustering(params: {
  min_cluster_size?: number;
  min_samples?: number;
  anomaly_ids?: string[];
}): Promise<unknown> {
  const { data } = await api.post("/cluster/trigger", params);
  return data;
}

export async function fetchClusterVisualization(): Promise<unknown> {
  const { data } = await api.get("/cluster/visualization");
  return data;
}

// ── Anomaly ──

export async function fetchAnomalies(params: {
  camera_id?: string;
  source?: string;
  status?: string;
  page?: number;
  page_size?: number;
}): Promise<AnomalyRecord[]> {
  const { data } = await api.get<AnomalyRecord[]>("/anomaly/list", {
    params,
  });
  return data;
}

export async function fetchAnomalyDetail(
  anomalyId: string
): Promise<AnomalyRecord> {
  const { data } = await api.get<AnomalyRecord>(`/anomaly/${anomalyId}`);
  return data;
}

export async function reprocessAnomaly(
  anomalyId: string
): Promise<unknown> {
  const { data } = await api.post(`/anomaly/${anomalyId}/reprocess`);
  return data;
}

export async function searchSimilar(
  anomalyId: string,
  topK = 20,
  threshold = 0.7
): Promise<unknown> {
  const { data } = await api.get("/embedding/search", {
    params: { anomaly_id: anomalyId, top_k: topK, threshold },
  });
  return data;
}

// ── Knowledge Base ──

export async function fetchKnowledgeEntries(params: {
  category?: string;
  defect_type?: string;
  page?: number;
  page_size?: number;
}): Promise<unknown[]> {
  const { data } = await api.get("/knowledge/entries", { params });
  return data;
}

export async function searchKnowledge(
  q: string,
  limit = 20
): Promise<unknown[]> {
  const { data } = await api.get("/knowledge/entries/search", {
    params: { q, limit },
  });
  return data;
}

export async function createKnowledgeEntry(
  entry: Record<string, unknown>
): Promise<unknown> {
  const { data } = await api.post("/knowledge/entries", entry);
  return data;
}

export async function deleteKnowledgeEntry(
  knowledgeId: string
): Promise<void> {
  await api.delete(`/knowledge/entries/${knowledgeId}`);
}

// ── Rules Engine ──

export async function fetchRules(params: {
  rule_type?: string;
  enabled?: boolean;
  page?: number;
  page_size?: number;
}): Promise<unknown[]> {
  const { data } = await api.get("/rules", { params });
  return data;
}

export async function createRule(params: Record<string, unknown>): Promise<unknown> {
  const { data } = await api.post("/rules", null, { params });
  return data;
}

export async function evaluateRules(params: {
  camera_id: string;
  defect_type?: string;
  anomaly_score?: number;
  classifier_prediction?: string;
}): Promise<unknown> {
  const { data } = await api.post("/rules/evaluate", null, { params });
  return data;
}

export async function toggleRule(
  ruleId: string,
  enabled: boolean
): Promise<unknown> {
  const { data } = await api.post(
    `/rules/${ruleId}/toggle?enabled=${enabled}`
  );
  return data;
}

export async function deleteRule(ruleId: string): Promise<void> {
  await api.delete(`/rules/${ruleId}`);
}

export async function generateRulesFromKnowledge(
  knowledgeEntryId: string
): Promise<unknown> {
  const { data } = await api.post(
    `/rules/generate-from-knowledge?knowledge_entry_id=${knowledgeEntryId}`
  );
  return data;
}

// ── Model Deploy ──

export async function deployModel(params: {
  model_name: string;
  version: string;
  target: string;
  deployed_by?: string;
}): Promise<unknown> {
  const { data } = await api.post("/model/deploy", params);
  return data;
}
