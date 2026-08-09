import { describe, it, expect } from 'vitest';
import { DEFAULT_PLAN, metaFor, plansForProvider } from '../lib/livePlanDefaults';

describe('livePlanDefaults', () => {
  it('auto-selects extended plans for github/google and readonly for notion', () => {
    expect(DEFAULT_PLAN.github).toBe('smoke-extended');
    expect(DEFAULT_PLAN.google).toBe('smoke-extended');
    expect(DEFAULT_PLAN.notion).toBe('readonly');
  });

  it('maps provider+plan to a yaml path', () => {
    expect(metaFor('github', 'smoke-extended')?.path).toBe(
      'configs/live/github_smoke_extended.yaml',
    );
    expect(metaFor('notion', 'readonly')?.path).toBe('configs/live/notion_readonly.yaml');
    expect(plansForProvider('notion').map((p) => p.kind)).toEqual(['readonly']);
  });
});
