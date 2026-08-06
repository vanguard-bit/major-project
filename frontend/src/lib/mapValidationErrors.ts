export function mapValidationErrorsToForm(err: unknown): Record<string, string> {
  const result: Record<string, string> = {};
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (!Array.isArray(detail)) return result;
  for (const item of detail) {
    const loc = (item as { loc?: unknown[]; msg?: string }).loc;
    const msg = (item as { msg?: string }).msg ?? 'Invalid';
    if (!Array.isArray(loc) || loc.length === 0) {
      result.non_field = msg;
      continue;
    }
    const strings = loc.filter((p): p is string => typeof p === 'string');
    const leaf = strings[strings.length - 1] ?? 'non_field';
    result[leaf] = msg;
  }
  return result;
}
