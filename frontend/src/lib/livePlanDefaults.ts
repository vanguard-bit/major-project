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
    label: 'smoke-extended (API-doc GETs)',
    path: 'configs/live/github_smoke_extended.yaml',
    description:
      '9 read-only GitHub REST calls from the official docs (PAT-safe); allowlist is /user only so extras become findings.',
  },
  {
    kind: 'smoke',
    label: 'smoke',
    path: 'configs/live/github_smoke.yaml',
    description: 'Short smoke: /user plus repos/orgs (paper-selected).',
  },
  {
    kind: 'readonly',
    label: 'readonly',
    path: 'configs/live/github_readonly.yaml',
    description: 'Single allowlisted GET /user — expect a clean risk score.',
  },
];

const GOOGLE_PLANS: LivePlanMeta[] = [
  {
    kind: 'smoke-extended',
    label: 'smoke-extended (API-doc GETs)',
    path: 'configs/live/google_smoke_extended.yaml',
    description:
      'Extra Google userinfo / Cloud Resource Manager / discovery GETs; allowlist is userinfo only.',
  },
  {
    kind: 'smoke',
    label: 'smoke',
    path: 'configs/live/google_smoke.yaml',
    description: 'userinfo + Cloud Resource Manager projects list (paper-selected).',
  },
  {
    kind: 'readonly',
    label: 'readonly',
    path: 'configs/live/google_readonly.yaml',
    description: 'Single allowlisted GET userinfo — expect a clean risk score.',
  },
];

const NOTION_PLANS: LivePlanMeta[] = [
  {
    kind: 'readonly',
    label: 'readonly',
    path: 'configs/live/notion_readonly.yaml',
    description: 'Single allowlisted GET /v1/users/me — expect a clean risk score.',
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
  notion: 'readonly',
};

export const FIELD_HELP = {
  provider:
    'Which SaaS to probe. Changing this auto-loads that provider’s YAML plan defaults.',
  plan: 'Committed live plan under configs/live/. Auto-selected when you change provider; you can still override.',
  planFile: 'Path to the YAML that will run (auto-filled from provider + plan).',
  token:
    'Paste a sandbox token only. Sent to localhost for this request, then cleared — never stored in the browser.',
} as const;

export function plansForProvider(provider: LiveProvider): LivePlanMeta[] {
  return BY_PROVIDER[provider];
}

export function metaFor(provider: LiveProvider, plan: LivePlanKind): LivePlanMeta | undefined {
  return plansForProvider(provider).find((p) => p.kind === plan);
}
