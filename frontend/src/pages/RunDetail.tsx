import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { getApiBaseUrl } from '../components/ApiClient';
import { useFindings, useRun } from '../components/useApiHooks';
import { useDemoMode } from '../hooks/useDemoMode';
import { TERMINAL_RUN_STATUSES } from '../types/api';

const MAX_POLL_MS = 5 * 60 * 1000;

export function RunDetail() {
  const { id = '' } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const pollStartedAt = useRef(Date.now());
  const [, setTick] = useState(0);
  const { enabled: demoEnabled } = useDemoMode();

  const runQuery = useRun(id);
  const findingsQuery = useFindings(id);

  const run = runQuery.data;
  const findings = run?.findings?.length
    ? run.findings
    : (findingsQuery.data ?? []);
  const isTerminal = !!run && TERMINAL_RUN_STATUSES.has(run.status);

  useEffect(() => {
    pollStartedAt.current = Date.now();
    setTick(0);

    if (isTerminal) return;
    const remaining = MAX_POLL_MS - (Date.now() - pollStartedAt.current);
    if (remaining <= 0) {
      setTick((n) => n + 1);
      return;
    }
    const t = window.setTimeout(() => setTick((n) => n + 1), remaining + 50);
    return () => window.clearTimeout(t);
  }, [isTerminal, id]);

  useEffect(() => {
    if (isTerminal && id) {
      void queryClient.invalidateQueries({ queryKey: ['findings', id] });
    }
  }, [isTerminal, id, queryClient]);

  const elapsed = Date.now() - pollStartedAt.current;
  const stillWaiting =
    !!run &&
    !isTerminal &&
    (elapsed > MAX_POLL_MS || runQuery.failureCount >= 5);

  function openReport() {
    window.open(`${getApiBaseUrl()}/runs/${id}/report?format=html`, '_blank');
  }

  if (!id) {
    return (
      <main>
        <p className="banner error">Missing run id.</p>
        <Link to="/">Back to Dashboard</Link>
      </main>
    );
  }

  return (
    <main>
      <p>
        <Link to="/">← Dashboard</Link>
        {' · '}
        <Link to="/targets">Targets</Link>
      </p>
      <h1>Run {id}</h1>

      {runQuery.isLoading && <p className="muted">Loading run…</p>}
      {runQuery.isError && (
        <p className="banner error">Could not load run. Check the id and try again.</p>
      )}

      {run && (
        <section className="panel" aria-labelledby="run-status-heading">
          <h2 id="run-status-heading">Status</h2>
          <p>
            <strong data-testid="run-status">{run.status}</strong>
            {' · '}
            <span className="muted">
              Last updated:{' '}
              {runQuery.dataUpdatedAt
                ? new Date(runQuery.dataUpdatedAt).toLocaleString()
                : '—'}
            </span>
          </p>
          <p className="muted">
            Target: {run.target?.name ?? '—'}
            {run.target?.environment ? ` (${run.target.environment})` : ''}
          </p>
          {stillWaiting && (
            <p className="banner info" role="status">
              Still waiting — refresh manually
              {' '}
              <button type="button" className="secondary" onClick={() => runQuery.refetch()}>
                Refresh
              </button>
            </p>
          )}
          <p>
            <button type="button" onClick={openReport}>
              Open report
            </button>
          </p>
        </section>
      )}

      <section className="panel" aria-labelledby="findings-heading">
        <h2 id="findings-heading">Findings</h2>
        {findingsQuery.isLoading && <p className="muted">Loading findings…</p>}
        {findingsQuery.isError && (
          <p className="banner error">Could not load findings.</p>
        )}
        {!findingsQuery.isLoading && findings.length === 0 && (
          <p className="muted">No findings yet.</p>
        )}
        {findings.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>Severity</th>
                <th>Category</th>
                <th>Endpoint</th>
                <th>Title</th>
              </tr>
            </thead>
            <tbody>
              {findings.map((f, i) => (
                <tr key={`${f.endpoint}-${f.title}-${i}`}>
                  <td>{f.severity}</td>
                  <td>{f.category}</td>
                  <td>{f.endpoint}</td>
                  <td>{f.title}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {demoEnabled && (
        <section className="panel demo-audit-panel" aria-labelledby="demo-audit-heading">
          <h2 id="demo-audit-heading">Demo audit</h2>
          <p className="banner error">
            Developer demo-only control — do not use in production.
          </p>
          <p>
            <a
              href={`http://localhost:8001/admin/audit/${id}`}
              target="_blank"
              rel="noreferrer"
            >
              Open mock SaaS audit for {id}
            </a>
          </p>
        </section>
      )}
    </main>
  );
}
