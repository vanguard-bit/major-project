import type {
  LiveEvidenceRow,
  LivePlanKind,
  LiveProbeResponse,
  LiveProvider,
} from '../types/api';

/** Extract sortable timestamp fragment from live run ids. */
export function runIdTimestamp(runId: string): string {
  const match = runId.match(/(\d{8}T\d+Z)/);
  return match?.[1] ?? runId;
}

export function compareRunIdsNewestFirst(a: string, b: string): number {
  return runIdTimestamp(b).localeCompare(runIdTimestamp(a));
}

/** Keep the newest artifact per plan_id. */
export function latestByPlanId(rows: LiveEvidenceRow[]): Map<string, LiveEvidenceRow> {
  const sorted = [...rows].sort((a, b) => compareRunIdsNewestFirst(a.run_id, b.run_id));
  const map = new Map<string, LiveEvidenceRow>();
  for (const row of sorted) {
    if (!map.has(row.plan_id)) map.set(row.plan_id, row);
  }
  return map;
}

export function newestRunId(rows: LiveEvidenceRow[]): string | null {
  if (rows.length === 0) return null;
  return [...rows].sort((a, b) => compareRunIdsNewestFirst(a.run_id, b.run_id))[0]
    ?.run_id ?? null;
}

function resultSummary(hidden: string[], risk: number): string {
  if (!hidden.length && risk === 0) return 'clean';
  if (hidden.length) return `hidden ${hidden.join(', ')}`;
  return `risk ${risk}`;
}

export function probeResponseToEvidenceRow(
  result: LiveProbeResponse,
): LiveEvidenceRow {
  const scenario =
    result.plan_id.includes('-')
      ? result.plan_id.slice(result.plan_id.indexOf('-') + 1)
      : result.plan_id;
  return {
    platform:
      result.provider === 'github'
        ? 'GitHub'
        : result.provider === 'google'
          ? 'Google'
          : result.provider === 'notion'
            ? 'Notion'
            : result.provider,
    scenario,
    risk_score: result.risk_score,
    result: resultSummary(result.hidden_endpoints, result.risk_score),
    run_id: result.run_id,
    plan_id: result.plan_id,
    hidden_endpoints: result.hidden_endpoints,
    reached_endpoints: result.reached_endpoints,
    findings: result.findings,
    hidden_endpoint_responses: result.hidden_endpoint_responses ?? [],
  };
}

export function planIdFor(provider: LiveProvider, plan: LivePlanKind): string {
  return `${provider}-${plan}`;
}

/** Merge a fresh probe into evidence: drop same run_id, prefer this row for its plan. */
export function mergeProbeIntoEvidence(
  existing: LiveEvidenceRow[] | undefined,
  result: LiveProbeResponse,
): LiveEvidenceRow[] {
  const fresh = probeResponseToEvidenceRow(result);
  const rest = (existing ?? []).filter(
    (row) => row.run_id !== fresh.run_id && row.plan_id !== fresh.plan_id,
  );
  return [fresh, ...rest];
}
