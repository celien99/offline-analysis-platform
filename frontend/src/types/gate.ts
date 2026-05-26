export interface GateEvaluationReport {
  gate_id: string;
  model_version_id: string;
  status: string;
  real_defect_recall: number | null;
  baseline_real_defect_recall: number | null;
  false_alarm_suppression_rate: number | null;
  baseline_false_alarm_suppression_rate: number | null;
  suppressed_real_defect_count: number | null;
  total_samples: number | null;
  real_defect_samples: number | null;
  false_alarm_samples: number | null;
  criteria: Record<string, unknown> | null;
  metrics: Record<string, unknown> | null;
  baseline_metrics: Record<string, unknown> | null;
  stratified_metrics: Array<Record<string, unknown>> | null;
  failure_reasons: string[] | null;
  evaluated_at: string;
  evaluated_by: string;
}

export interface GateStatus {
  model_version_id: string;
  model_status: string;
  gate_status: string | null;
  gate_passed: boolean;
  message: string;
}
