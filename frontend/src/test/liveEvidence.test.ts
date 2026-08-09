import { describe, it, expect } from 'vitest';
import {
  compareRunIdsNewestFirst,
  latestByPlanId,
  mergeProbeIntoEvidence,
  probeResponseToEvidenceRow,
} from '../lib/liveEvidence';
import type { LiveEvidenceRow } from '../types/api';

const older: LiveEvidenceRow = {
  platform: 'GitHub',
  scenario: 'smoke',
  risk_score: 10,
  result: 'clean',
  run_id: 'github-smoke-20260809T140000000000Z-aaaaaa',
  plan_id: 'github-smoke',
  hidden_endpoints: [],
  reached_endpoints: ['/user'],
  findings: [],
};

const newer: LiveEvidenceRow = {
  ...older,
  risk_score: 50,
  result: 'hidden /user/orgs',
  run_id: 'github-smoke-20260809T150000000000Z-bbbbbb',
  hidden_endpoints: ['/user/orgs'],
};

describe('liveEvidence helpers', () => {
  it('picks newest run per plan_id by timestamp in run_id', () => {
    const map = latestByPlanId([older, newer]);
    expect(map.get('github-smoke')?.run_id).toBe(newer.run_id);
    expect(compareRunIdsNewestFirst(older.run_id, newer.run_id)).toBeGreaterThan(0);
  });

  it('mergeProbeIntoEvidence replaces prior artifact for that plan only', () => {
    const other: LiveEvidenceRow = {
      platform: 'Google',
      scenario: 'readonly',
      risk_score: 0,
      result: 'clean',
      run_id: 'google-readonly-20260809T120000000000Z-cccccc',
      plan_id: 'google-readonly',
      hidden_endpoints: [],
      reached_endpoints: [],
      findings: [],
    };
    const merged = mergeProbeIntoEvidence([older, other], {
      run_id: 'github-smoke-20260809T160000000000Z-dddddd',
      provider: 'github',
      plan_id: 'github-smoke',
      status: 'completed',
      risk_score: 75,
      hidden_endpoints: ['/user/repos'],
      reached_endpoints: ['/user', '/user/repos'],
      findings: [],
    });
    expect(merged).toHaveLength(2);
    expect(merged.find((r) => r.plan_id === 'github-smoke')?.risk_score).toBe(75);
    expect(merged.find((r) => r.plan_id === 'google-readonly')).toEqual(other);
    expect(probeResponseToEvidenceRow({
      run_id: 'x',
      provider: 'notion',
      plan_id: 'notion-smoke',
      status: 'completed',
      risk_score: 0,
      hidden_endpoints: [],
      reached_endpoints: [],
      findings: [],
    }).platform).toBe('Notion');
  });
});
