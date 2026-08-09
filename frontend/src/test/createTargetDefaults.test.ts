import { describe, it, expect } from 'vitest';
import { defaultsFromBaseUrl, normalizeBaseUrl } from '../lib/createTargetDefaults';

describe('createTargetDefaults', () => {
  it('normalizes trailing slash and builds sync/audit defaults', () => {
    expect(normalizeBaseUrl('http://127.0.0.1:8001/')).toBe('http://127.0.0.1:8001');
    expect(defaultsFromBaseUrl('http://127.0.0.1:8001/')).toEqual({
      integration_sync_url: 'http://127.0.0.1:8001/sync',
      audit_base_url: 'http://127.0.0.1:8001',
    });
  });

  it('returns null for missing protocol', () => {
    expect(defaultsFromBaseUrl('example.test')).toBeNull();
  });
});
