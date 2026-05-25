import { get, post } from "./client";
import type { DeploymentRecord, DeployRequest, ModelOption, ModelRegisterData } from "../types";

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
};
