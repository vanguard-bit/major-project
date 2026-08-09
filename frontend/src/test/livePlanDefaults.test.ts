import { describe, it, expect } from 'vitest';
import { DEFAULT_PLAN, metaFor, plansForProvider } from '../lib/livePlanDefaults';

describe('livePlanDefaults', () => {
  it('auto-selects extended plans for all providers', () => {
    expect(DEFAULT_PLAN.github).toBe('smoke-extended');
    expect(DEFAULT_PLAN.google).toBe('smoke-extended');
    expect(DEFAULT_PLAN.notion).toBe('smoke-extended');
  });

  it('maps provider+plan to a yaml path', () => {
    expect(metaFor('github', 'smoke-extended')?.path).toBe(
      'configs/live/github_smoke_extended.yaml',
    );
    expect(metaFor('notion', 'readonly')?.path).toBe('configs/live/notion_readonly.yaml');
    expect(metaFor('notion', 'smoke')?.path).toBe('configs/live/notion_smoke.yaml');
    expect(plansForProvider('notion').map((p) => p.kind)).toEqual([
      'smoke-extended',
      'smoke',
      'readonly',
    ]);
  });
});
