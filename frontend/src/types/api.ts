export type AuthType = 'static_token' | 'oauth_client_credentials';

export interface TokenConfig {
  token?: string | null;
  token_url?: string | null;
  client_id?: string | null;
  client_secret?: string | null;
  scope?: string | null;
}

export interface TargetConfig {
  name: string;
  environment?: string;
  base_url: string;
  integration_sync_url: string;
  audit_base_url: string;
  auth_type?: AuthType;
  token_config?: TokenConfig;
  openapi_paths?: string[];
  seed_endpoints?: string[];
  expected_endpoints?: string[];
  expected_scopes?: string[];
  sensitive_markers?: string[];
  description?: string;
}

export interface TestRunConfig {
  crawl_depth?: number;
  mutation_budget?: number;
  taint_fields?: string[];
  replay_count?: number;
  timeout_seconds?: number;
  rate_limit_per_minute?: number;
  safety_mode?: boolean;
}

export interface Finding {
  severity: 'low' | 'medium' | 'high' | 'critical';
  category:
    | 'hidden_endpoint'
    | 'sensitive_field_access'
    | 'behavioral_divergence'
    | 'policy_violation';
  endpoint: string;
  title: string;
  evidence: string;
  expected_behavior: string;
  observed_behavior: string;
  confidence?: number;
  remediation_note?: string;
}

export interface RunReport {
  run_id: string;
  target_name: string;
  status: string;
  reached_endpoints: string[];
  hidden_endpoints: string[];
  sensitive_fields_accessed: string[];
  divergence_summary: string[];
  risk_score: number;
  findings: Finding[];
}

export interface RunRecord {
  run_id: string;
  status: string;
  target: TargetConfig;
  config: TestRunConfig;
  findings: Finding[];
  exchanges: unknown[];
  report?: RunReport | null;
}

export const TERMINAL_RUN_STATUSES = new Set([
  'completed',
  'failed',
  'error',
  'cancelled',
]);

export type RecentRunEntry = {
  runId: string;
  startedAt: string;
  targetName?: string;
};

export type LiveProvider = 'github' | 'google' | 'notion';
export type LivePlanKind = 'smoke' | 'readonly' | 'smoke-extended';

export interface HiddenEndpointResponse {
  path: string;
  status_code: number;
  response_bytes: number;
  response_fields: string[];
  content_type?: string | null;
}

export interface LiveEvidenceRow {
  platform: string;
  scenario: string;
  risk_score: number;
  result: string;
  run_id: string;
  plan_id: string;
  hidden_endpoints: string[];
  reached_endpoints: string[];
  findings: Finding[];
  hidden_endpoint_responses?: HiddenEndpointResponse[];
}

export interface LiveProbeRequest {
  provider: LiveProvider;
  plan: LivePlanKind;
  token: string;
}

export interface LiveProbeResponse {
  run_id: string;
  provider: string;
  plan_id: string;
  status: string;
  risk_score: number;
  hidden_endpoints: string[];
  reached_endpoints: string[];
  findings: Finding[];
  hidden_endpoint_responses?: HiddenEndpointResponse[];
}
