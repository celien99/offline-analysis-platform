export interface VLMResult {
  anomaly_type: string;
  is_false_alarm: boolean;
  reason: string;
  confidence: number;
  suggestion: string;
  raw_response?: string;
}

export interface VLMAnalysisResponse {
  status: string;
  cluster_id?: string;
  anomaly_id?: string;
  result?: VLMResult;
  error?: string;
}

export interface VLMBatchAnalysisResponse {
  status: string;
  total: number;
  results: VLMAnalysisResponse[];
}

/** POST /api/multimodal/analyze/anomaly/{id} 响应 */
export interface VLMAnomalyAnalysisResponse {
  status: string;
  anomaly_id: string;
  result?: VLMResult;
  error?: string;
}
