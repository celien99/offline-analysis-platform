import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { clusterApi, anomalyApi, knowledgeApi, rulesApi } from "../api";
import type { ReviewSubmit } from "../types";

// ── Cluster queries ──

export function useClusterList(page: number) {
  return useQuery({
    queryKey: ["clusters", "list", page],
    queryFn: ({ signal }) => clusterApi.list(page, 20, undefined, signal),
    placeholderData: (prev) => prev,
  });
}

export function useClusterDetail(clusterId: string | null) {
  return useQuery({
    queryKey: ["clusters", "detail", clusterId],
    queryFn: ({ signal }) => clusterApi.detail(clusterId!, signal),
    enabled: !!clusterId,
  });
}

export function useClusterVisualization() {
  return useQuery({
    queryKey: ["clusters", "visualization"],
    queryFn: ({ signal }) => clusterApi.visualization(signal),
    staleTime: 60_000,
  });
}

export function useClusterReview() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (review: ReviewSubmit) => clusterApi.review(review),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["clusters"] });
    },
  });
}

// ── Anomaly queries ──

export function useAnomalyList(params: {
  page: number;
  camera_id?: string;
  status?: string;
}) {
  return useQuery({
    queryKey: ["anomalies", "list", params],
    queryFn: ({ signal }) =>
      anomalyApi.list({ page_size: 20, ...params }, signal),
    placeholderData: (prev) => prev,
  });
}

export function useAnomalyReprocess() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (anomalyId: string) => anomalyApi.reprocess(anomalyId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["anomalies"] });
    },
  });
}

// ── Knowledge queries ──

export function useKnowledgeList(
  params: { category?: string; defect_type?: string },
  enabled = true,
) {
  return useQuery({
    queryKey: ["knowledge", "list", params],
    queryFn: ({ signal }) =>
      knowledgeApi.list({ page_size: 100, ...params }, signal),
    placeholderData: (prev) => prev,
    enabled,
  });
}

export function useKnowledgeSearch(keyword: string, enabled = true) {
  return useQuery({
    queryKey: ["knowledge", "search", keyword],
    queryFn: ({ signal }) => knowledgeApi.search(keyword, 20, signal),
    enabled: enabled && keyword.length > 0,
  });
}

export function useKnowledgeCreate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (entry: Record<string, unknown>) => knowledgeApi.create(entry),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge"] });
    },
  });
}

export function useKnowledgeDelete() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (knowledgeId: string) => knowledgeApi.delete(knowledgeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge"] });
    },
  });
}

// ── Rules queries ──

export function useRulesList(typeFilter?: string) {
  return useQuery({
    queryKey: ["rules", "list", typeFilter],
    queryFn: ({ signal }) =>
      rulesApi.list({ rule_type: typeFilter, page_size: 200 }, signal),
    placeholderData: (prev) => prev,
  });
}

export function useRuleCreate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: Record<string, unknown>) => rulesApi.create(params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rules"] });
    },
  });
}

export function useRuleToggle() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ ruleId, enabled }: { ruleId: string; enabled: boolean }) =>
      rulesApi.toggle(ruleId, enabled),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rules"] });
    },
  });
}

export function useRuleDelete() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ruleId: string) => rulesApi.delete(ruleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rules"] });
    },
  });
}

export function useRuleEvaluate() {
  return useMutation({
    mutationFn: (params: {
      camera_id: string;
      defect_type?: string;
      anomaly_score?: number;
      classifier_prediction?: string;
    }) => rulesApi.evaluate(params),
  });
}

export function useRuleGenerateFromKb() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (knowledgeEntryId: string) =>
      rulesApi.generateFromKnowledge(knowledgeEntryId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rules"] });
    },
  });
}
