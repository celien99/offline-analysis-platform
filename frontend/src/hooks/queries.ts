import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { clusterApi, anomalyApi, knowledgeApi, rulesApi, trainingApi, modelApi, multimodalApi, patchcoreTrainingApi, inspectionApi } from "../api";
import type { ReviewSubmit, TrainingStartParams, DeployRequest } from "../types";

// ── Cluster queries ──

export function useClusterList(page: number, enabled = true) {
  return useQuery({
    queryKey: ["clusters", "list", page],
    queryFn: ({ signal }) => clusterApi.list(page, 20, undefined, signal),
    placeholderData: (prev) => prev,
    enabled,
  });
}

export function useClusterDetail(clusterId: string | null) {
  return useQuery({
    queryKey: ["clusters", "detail", clusterId],
    queryFn: ({ signal }) => clusterApi.detail(clusterId!, signal),
    enabled: !!clusterId,
  });
}

export function useClusterAnomalies(clusterId: string | null) {
  return useQuery({
    queryKey: ["clusters", "anomalies", clusterId],
    queryFn: ({ signal }) => clusterApi.anomalies(clusterId!, signal),
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
    select: (data) => data.items,
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
      rulesApi.list({ rule_type: typeFilter, page_size: 100 }, signal),
    placeholderData: (prev) => prev,
    select: (data) => data.items,
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

export function useRuleDeploy() {
  return useMutation({
    mutationFn: (target: string = "production_line_a") =>
      rulesApi.deploy(target),
  });
}

// ── Training queries ──

export function useTrainingStart() {
  return useMutation({
    mutationFn: (params: TrainingStartParams) => trainingApi.start(params),
  });
}

export function useTrainingStatus(taskId: string | null) {
  return useQuery({
    queryKey: ["training", "status", taskId],
    queryFn: ({ signal }) => trainingApi.status(taskId!, signal),
    enabled: !!taskId,
    refetchInterval: (query) => {
      const status = (query.state.data as { status?: string } | undefined)?.status;
      if (status === "success" || status === "failed" || status === "SUCCESS" || status === "FAILURE") {
        return false;
      }
      return 5_000;
    },
  });
}

export function useTrainedModels(params: {
  model_type?: string;
  page?: number;
} = {}) {
  return useQuery({
    queryKey: ["training", "models", params],
    queryFn: ({ signal }) => trainingApi.listModels({ page_size: 20, ...params }, signal),
    placeholderData: (prev) => prev,
  });
}

// ── Model deployment queries ──

export function useDeployments(params: {
  target?: string;
  page?: number;
} = {}) {
  return useQuery({
    queryKey: ["model", "deployments", params],
    queryFn: ({ signal }) => modelApi.listDeployments({ page_size: 50, ...params }, signal),
    placeholderData: (prev) => prev,
  });
}

export function useDeployModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: DeployRequest) => modelApi.deploy(params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["model"] });
    },
  });
}

export function useRollbackModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ target, reason }: { target: string; reason?: string }) =>
      modelApi.rollback(target, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["model"] });
    },
  });
}

// ── Multimodal (VLM) queries ──

export function useVLMAnalyzeCluster() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (clusterId: string) => multimodalApi.analyzeCluster(clusterId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["clusters"] });
    },
  });
}

export function useVLMAnalyzeBatch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (clusterIds: string[]) => multimodalApi.analyzeBatch(clusterIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["clusters"] });
    },
  });
}

export function useVLMAnalyzeAnomaly() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (anomalyId: string) => multimodalApi.analyzeAnomaly(anomalyId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["anomalies"] });
    },
  });
}

// ── PatchCore Training hooks ──

export function usePatchCoreTrainingStart() {
  return useMutation({
    mutationFn: (formData: FormData) => patchcoreTrainingApi.start(formData),
  });
}

// ── Inspection hooks ──

export function useInspectionRun() {
  return useMutation({
    mutationFn: (formData: FormData) => inspectionApi.run(formData),
  });
}

export function useInspectionResult(taskId: string | null) {
  return useQuery({
    queryKey: ["inspection", "result", taskId],
    queryFn: ({ signal }) => inspectionApi.result(taskId!, signal),
    enabled: !!taskId,
    refetchInterval: (query) =>
      query.state.data?.status === "SUCCESS" || query.state.data?.status === "FAILURE"
        ? false
        : 3000,
  });
}
