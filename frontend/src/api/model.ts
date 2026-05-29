import { get, post } from "./client";
import type { DeploymentRecord, DeployRequest, ModelOption, ModelRegisterData } from "../types";

export interface BatchTrainImportRequest {
  output_root: string;
  seat_model_id: string;
  auto_bind?: boolean;
}

export interface BatchTrainImportResult {
  status: string;
  imported: Array<{
    camera_id: string;
    model_type: string;
    model_id: string;
    model_name: string;
    file: string;
    bound?: boolean;
  }>;
  errors: string[];
}

export const modelApi = {
  deploy: (params: DeployRequest, signal?: AbortSignal) =>
    post<DeploymentRecord>("/model/deploy", params, { signal }),

  rollback: (target: string, reason?: string, signal?: AbortSignal) =>
    post(`/model/deploy/${target}/rollback`, { reason }, { signal }),

  listDeployments: (params: {
    target?: string;
    page?: number;
    page_size?: number;
  }, signal?: AbortSignal) =>
    get<DeploymentRecord[]>("/model/deployments", { params, signal }),

  getDeployTargets: (signal?: AbortSignal) =>
    get<Record<string, string>>("/model/deploy-targets", { signal }),

  /** 获取已注册模型列表，供下拉框使用 */
  listOptions: (modelType?: string, signal?: AbortSignal) =>
    get<ModelOption[]>("/model/options", { params: { model_type: modelType }, signal }),

  /** 手动注册外部模型 */
  register: (data: ModelRegisterData) =>
    post<ModelOption>("/model/register", data),

  /** 批量导入 batch_train 产物 */
  importBatchTrain: (data: BatchTrainImportRequest) =>
    post<BatchTrainImportResult>("/model/import-batch-train", data),
};
