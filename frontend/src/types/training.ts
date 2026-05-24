export interface TrainingStartParams {
  model_type?: "mobilenet_v3_small" | "efficientnet_b0" | "resnet18";
  num_classes?: number;
  batch_size?: number;
  epochs?: number;
  learning_rate?: number;
  validation_split?: number;
  class_names?: string[];
  augmentations?: boolean;
  anomaly_ids?: string[] | null;
}

export interface TrainingStatus {
  task_id: string;
  status: string;
  model_name?: string | null;
  model_version?: string | null;
  progress?: number | null;
  current_epoch?: number | null;
  total_epochs?: number | null;
  metrics?: Record<string, number> | null;
  error_message?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface TrainedModel {
  model_id: string;
  model_name: string;
  version: string;
  model_type: string;
  framework: string;
  status: string;
  trained_at: string | null;
}

export interface TrainedModelList {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  models: TrainedModel[];
}
