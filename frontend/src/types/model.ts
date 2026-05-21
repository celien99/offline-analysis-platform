export interface DeployRequest {
  model_name: string;
  version: string;
  target: string;
  deployed_by?: string | null;
}

export interface DeploymentRecord {
  deployment_id: string;
  model_version_id: string;
  model_name?: string | null;
  version?: string | null;
  target: string;
  deployed_by: string | null;
  deployed_at: string;
  previous_version: string | null;
  deployment_status: string;
}
