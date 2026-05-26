import { get } from "./client";

export interface HotReloadTarget {
  target: string;
  active_model: string | null;
  active_version: string | null;
  active_checksum: string | null;
  checksum_verified: boolean;
  has_shadow: boolean;
  rollback_version: string | null;
  has_pending_reload: boolean;
  model_deployed: boolean;
}

export const hotReloadApi = {
  listTargets: (signal?: AbortSignal) =>
    get<{ total: number; targets: HotReloadTarget[] }>("/hot-reload/targets", { signal }),
};
