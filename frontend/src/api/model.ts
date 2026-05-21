import { get, post } from "./client";
import type { DeploymentRecord, DeployRequest } from "../types";

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
};
