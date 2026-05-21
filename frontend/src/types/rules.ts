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
