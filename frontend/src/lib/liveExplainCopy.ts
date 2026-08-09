import type { ExplainSections } from '../components/ExplainPanel';

export const LIVE_TRANSITION = {
  lead:
    'Same analysis model as the mock demo — now against real software-as-a-service application programming interfaces with sandbox tokens you paste locally.',
  sections: {
    what: 'Act 2 of the faculty demo: live probes against GitHub, Google, and Notion using committed plan configuration files.',
    why: 'Shows the tool is not mock-only: the allowlist-versus-traffic story holds on production application programming interface shapes.',
    whatAitDoes:
      'Runs read-only plan steps with your pasted token, records traffic, diffs against the plan allowlist, and stores artifacts under results/derived.',
  } satisfies ExplainSections,
};

export const LIVE_PROBE_FORM = {
  lead:
    'Pick provider and plan (the plan file path auto-fills). Paste a sandbox token only when you want to run a fresh probe.',
  sections: {
    what: 'The live probe control surface for GitHub, Google, and Notion. Plan flavors: readonly is a narrow allowlist check that should stay clean when the token works; smoke is a short finding demo; smoke-extended adds more documentation read requests outside that narrow allowlist.',
    why: 'Lets you re-run a cell during questions and answers without leaving the Live page. Use readonly when you want to show a clean score; use smoke or smoke-extended when you want visible hidden-endpoint findings.',
    whatAitDoes:
      'Sends the provider, plan, and token to the demo-gated live probe endpoint; returns risk, hidden endpoints, and findings.',
  } satisfies ExplainSections,
};

export const LIVE_RESULTS = {
  lead:
    'Completed sandbox probes across GitHub, Google, and Notion. Click a matrix cell for detail; turn on Screenshot mode in the top bar to show the summary table for slides.',
  sections: {
    what: 'A risk matrix of provider × plan cells, plus one detail panel for the selected plan. readonly cells are the clean allowlist baseline; smoke and smoke-extended usually show higher risk when extra paths were reached.',
    why: 'Keeps the walkthrough focused on one plan’s evidence, while Screenshot mode exposes the full summary table for capture.',
    whatAitDoes:
      'Loads live evidence from the coordinator (demo live probes enabled), keeps only the latest run per plan, and shows risk and findings for the selected cell.',
  } satisfies ExplainSections,
};

export const LIVE_ADVANCED = {
  lead:
    'Prior-run dump and raw identifiers for rehearsal digressions — optional during the happy path.',
  sections: {
    what: 'A table of prior live evidence rows (platform, scenario, risk, result) with click-to-detail.',
    why: 'Useful if someone asks for a specific historical run identifier during questions and answers.',
    whatAitDoes:
      'Same evidence feed as the results board, presented as a chronological list.',
  } satisfies ExplainSections,
};
