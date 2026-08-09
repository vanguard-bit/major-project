import type { LivePlanKind, LiveProvider } from '../types/api';

export type LivePlanMeta = {
  kind: LivePlanKind;
  label: string;
  path: string;
  description: string;
};

const GITHUB_PLANS: LivePlanMeta[] = [
  {
    kind: 'smoke-extended',
    label: 'smoke-extended (documentation read requests)',
    path: 'configs/live/github_smoke_extended.yaml',
    description:
      'Nine read-only GitHub requests from the official documentation (safe for a personal access token); allowlist is /user only so extras become findings.',
  },
  {
    kind: 'smoke',
    label: 'smoke',
    path: 'configs/live/github_smoke.yaml',
    description: 'Short smoke: /user plus repositories and organizations (paper-selected).',
  },
  {
    kind: 'readonly',
    label: 'readonly',
    path: 'configs/live/github_readonly.yaml',
    description: 'Single allowlisted read of /user — expect a clean risk score.',
  },
];

const GOOGLE_PLANS: LivePlanMeta[] = [
  {
    kind: 'smoke-extended',
    label: 'smoke-extended (documentation read requests)',
    path: 'configs/live/google_smoke_extended.yaml',
    description:
      'Extra Google userinfo, Cloud Resource Manager, and discovery read requests; allowlist is userinfo only.',
  },
  {
    kind: 'smoke',
    label: 'smoke',
    path: 'configs/live/google_smoke.yaml',
    description: 'userinfo plus Cloud Resource Manager projects list (paper-selected).',
  },
  {
    kind: 'readonly',
    label: 'readonly',
    path: 'configs/live/google_readonly.yaml',
    description: 'Single allowlisted read of userinfo — expect a clean risk score.',
  },
];

const NOTION_PLANS: LivePlanMeta[] = [
  {
    kind: 'smoke-extended',
    label: 'smoke-extended (documentation read requests)',
    path: 'configs/live/notion_smoke_extended.yaml',
    description:
      'users/me, list users, and file uploads; allowlist is /v1/users/me only so extras become findings.',
  },
  {
    kind: 'smoke',
    label: 'smoke',
    path: 'configs/live/notion_smoke.yaml',
    description: 'users/me plus list users (short finding demo).',
  },
  {
    kind: 'readonly',
    label: 'readonly',
    path: 'configs/live/notion_readonly.yaml',
    description: 'Single allowlisted read of /v1/users/me — expect a clean risk score.',
  },
];

const BY_PROVIDER: Record<LiveProvider, LivePlanMeta[]> = {
  github: GITHUB_PLANS,
  google: GOOGLE_PLANS,
  notion: NOTION_PLANS,
};

export const DEFAULT_PLAN: Record<LiveProvider, LivePlanKind> = {
  github: 'smoke-extended',
  google: 'smoke-extended',
  notion: 'smoke-extended',
};

/** Fixed matrix for Results board (provider × plan). */
export const RESULTS_MATRIX: { provider: LiveProvider; plan: LivePlanKind }[] = [
  { provider: 'github', plan: 'readonly' },
  { provider: 'github', plan: 'smoke' },
  { provider: 'github', plan: 'smoke-extended' },
  { provider: 'google', plan: 'readonly' },
  { provider: 'google', plan: 'smoke' },
  { provider: 'google', plan: 'smoke-extended' },
  { provider: 'notion', plan: 'readonly' },
  { provider: 'notion', plan: 'smoke' },
  { provider: 'notion', plan: 'smoke-extended' },
];

export const FIELD_HELP = {
  provider:
    'Which software-as-a-service product to probe. Changing this auto-loads that provider’s plan file defaults.',
  plan: 'Committed live plan under configs/live/. Auto-selected when you change provider; you can still override.',
  planFile:
    'Path to the plan configuration file that will run (auto-filled from provider and plan).',
  token:
    'Paste a sandbox token only. Sent to localhost for this request, then cleared — never stored in the browser.',
} as const;

export function plansForProvider(provider: LiveProvider): LivePlanMeta[] {
  return BY_PROVIDER[provider];
}

export function metaFor(provider: LiveProvider, plan: LivePlanKind): LivePlanMeta | undefined {
  return plansForProvider(provider).find((p) => p.kind === plan);
}
