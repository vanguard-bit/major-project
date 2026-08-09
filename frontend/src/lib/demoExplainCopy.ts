import type { ExplainSections } from '../components/ExplainPanel';

export const DEMO_WHY = {
  lead:
    'Adversarial Integration Tester checks whether an integration’s observed Hypertext Transfer Protocol traffic stays inside the policy allowlist the vendor declared — and scores what leaks out.',
  sections: {
    what: 'Adversarial Integration Tester is a research demo that compares captured software-as-a-service and integration traffic to a declared allowlist policy. A hidden endpoint is a path the integration actually called that was never listed in that allowlist — for example billing — so the tool flags it as undeclared behavior.',
    why: 'Faculty and auditors care about undeclared endpoints and sensitive fields that policy documents never mention — not just whether the application programming interface “works.” Hidden endpoints are the clearest signal that the real traffic exceeded the declared contract.',
    whatAitDoes:
      'It runs a controlled assessment, records requests, diffs them against the allowlist, and emits findings plus a risk score when hidden endpoints or sensitive fields appear.',
  } satisfies ExplainSections,
};

export const DEMO_THIS_ACT = {
  lead:
    'This act uses a mock customer relationship management system and a seeded demo-integration target so you can show findings without touching production software-as-a-service products.',
  sections: {
    what: 'A local mock customer relationship management service (typically port 8001) plus a demo integration (port 8002) that deliberately reaches an undeclared billing path.',
    why: 'Faculty need to see the full loop — start run → traffic → allowlist miss → risk — before trusting live probes.',
    whatAitDoes:
      'Starts an assessment against demo-integration, captures Hypertext Transfer Protocol traffic, and surfaces hidden endpoints, sensitive fields, and divergence.',
  } satisfies ExplainSections,
};

export const DEMO_POLICY = {
  lead:
    'Seeded policy for demo-integration allows the declared customer relationship management sync paths; the undeclared billing call is what should light up as a finding.',
  sections: {
    what: 'A policy allowlist attached to the demo-integration target: permitted methods and paths the integration claims to use.',
    why: 'Without a declared allowlist there is nothing to diverge from — risk scoring needs a contract.',
    whatAitDoes:
      'Loads the target policy, compares each observed request, and flags endpoints (and fields) outside that contract.',
  } satisfies ExplainSections,
};

export const DEMO_OUTCOME = {
  lead:
    'After a run, Adversarial Integration Tester shows risk, findings, and a run detail page with the report so you can walk the evidence on screen.',
  sections: {
    what: 'The assessment result for the demo-integration run you just started (or a recent run from this browser).',
    why: 'The story beats a slide deck: open the run, show hidden endpoint and risk, then hand off to Live.',
    whatAitDoes:
      'Persists the run, lists findings with severity, and exposes report artifacts the coordinator already knows how to serve.',
  } satisfies ExplainSections,
};

export const DEMO_NEXT = {
  lead:
    'Same findings model next — real GitHub, Google, and Notion with sandbox tokens you paste.',
  sections: {
    what: 'A navigation handoff into Act 2 (Live).',
    why: 'Faculty usually ask whether this works on real application programming interfaces — Live answers with completed sandbox probes.',
    whatAitDoes:
      'Nothing new yet; it reuses the same risk and findings vocabulary on live evidence.',
  } satisfies ExplainSections,
};

export const DEMO_ADVANCED = {
  lead:
    'Optional tooling: create a custom target, open a run by identifier, or toggle demo mode — not required for the happy path.',
  sections: {
    what: 'Collapsed utilities formerly split across Dashboard and Targets.',
    why: 'Keeps the main story short while still supporting rehearsal edge cases and questions-and-answers digressions.',
    whatAitDoes:
      'Create target posts a new policy target; Open run navigates to the run detail page; Demo mode adjusts presentation helpers in this application.',
  } satisfies ExplainSections,
};
