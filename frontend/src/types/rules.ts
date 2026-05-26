export interface Rule {
  rule_id: string;
  name: string;
  rule_type: string;
  priority: number;
  enabled: boolean;
  description: string | null;
  created_at: string;
}

export interface MatchedRule {
  rule_id: string;
  name: string;
  type: string;
  priority: number;
}

export interface EvalResult {
  action: string;
  matched_rules: MatchedRule[];
  rule_count: number;
}

/** POST /api/rules 响应 */
export interface RuleCreateResponse {
  status: string;
  rule_id: string;
}

/** POST /api/rules/{id}/toggle 响应 */
export interface RuleToggleResponse {
  status: string;
  message?: string | null;
}

/** GET /api/rules/preview 单条记录 */
export interface RulePreviewItem {
  rule_id: string;
  name: string;
  rule_type: string;
  priority: number;
  enabled: boolean;
  description?: string | null;
  [key: string]: unknown;
}
