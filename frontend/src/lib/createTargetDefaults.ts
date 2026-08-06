export function normalizeBaseUrl(baseUrl: string): string | null {
  try {
    const url = new URL(baseUrl);
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return null;
    const path = url.pathname.replace(/\/+$/, '');
    return `${url.origin}${path === '/' ? '' : path}`;
  } catch {
    return null;
  }
}

export function defaultsFromBaseUrl(
  baseUrl: string,
): { integration_sync_url: string; audit_base_url: string } | null {
  const normalized = normalizeBaseUrl(baseUrl);
  if (!normalized) return null;
  return {
    integration_sync_url: `${normalized}/sync`,
    audit_base_url: normalized,
  };
}
