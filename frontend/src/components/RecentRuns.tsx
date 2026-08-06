import { useEffect, useMemo } from 'react';
import { useQueries } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { api } from './ApiClient';
import { useRecentRuns } from '../hooks/useRecentRuns';
import type { RunRecord } from '../types/api';

function statusLabel(
  result: { data?: RunRecord; isError: boolean; isPending: boolean; error: unknown } | undefined,
): string {
  if (!result) return '…';
  if (result.data) return result.data.status;
  if (result.isPending) return 'loading…';
  if (result.isError) {
    if (axios.isAxiosError(result.error) && result.error.response?.status === 404) {
      return '…';
    }
    return 'status unavailable';
  }
  return '…';
}

export function RecentRuns() {
  const { entries, remove, clear } = useRecentRuns();

  const queries = useQueries({
    queries: entries.map((entry) => ({
      queryKey: ['run', entry.runId] as const,
      queryFn: () => api.get(`/runs/${entry.runId}`).then((r) => r.data as RunRecord),
      staleTime: 3000,
      retry: (count: number, error: unknown) => {
        if (axios.isAxiosError(error) && error.response?.status === 404) return false;
        return count < 2;
      },
    })),
  });

  const notFoundIds = useMemo(
    () =>
      entries
        .filter((_, i) => {
          const result = queries[i];
          return (
            result?.isError &&
            axios.isAxiosError(result.error) &&
            result.error.response?.status === 404
          );
        })
        .map((e) => e.runId)
        .join(','),
    [entries, queries],
  );

  useEffect(() => {
    if (!notFoundIds) return;
    for (const runId of notFoundIds.split(',')) {
      remove(runId);
    }
  }, [notFoundIds, remove]);

  if (entries.length === 0) return null;

  return (
    <section className="recent-runs" aria-labelledby="recent-runs-heading">
      <div className="recent-runs-header">
        <h2 id="recent-runs-heading">Recent runs</h2>
        <button type="button" className="secondary" onClick={clear}>
          Clear recent runs
        </button>
      </div>
      <ul className="recent-runs-list">
        {entries.map((entry, i) => (
          <li key={entry.runId}>
            <Link to={`/runs/${entry.runId}`}>{entry.runId}</Link>
            {entry.targetName ? <span> — {entry.targetName}</span> : null}
            <span className="muted"> — {statusLabel(queries[i])}</span>
            {entry.startedAt ? (
              <span className="muted"> ({new Date(entry.startedAt).toLocaleString()})</span>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
