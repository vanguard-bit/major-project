import { FormEvent, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { DemoModeToggle } from '../components/DemoModeToggle';
import { RecentRuns } from '../components/RecentRuns';
import { useHealth, useTargets } from '../components/useApiHooks';

export function Dashboard() {
  const navigate = useNavigate();
  const health = useHealth();
  const targets = useTargets();
  const [runId, setRunId] = useState('');

  function handleOpenRun(e: FormEvent) {
    e.preventDefault();
    const id = runId.trim();
    if (!id) return;
    navigate(`/runs/${id}`);
  }

  const healthStatus = health.data?.status ?? (health.isError ? 'unreachable' : '…');
  const healthClass =
    healthStatus === 'ok' || healthStatus === 'healthy'
      ? 'health-badge ok'
      : health.isError
        ? 'health-badge error'
        : 'health-badge';

  const preview = (targets.data ?? []).slice(0, 5);

  return (
    <main>
      <h1>Dashboard</h1>

      <section className="panel" aria-labelledby="health-heading">
        <h2 id="health-heading">API health</h2>
        <p>
          Status:{' '}
          <span className={healthClass} data-testid="health-badge">
            {health.isLoading ? 'checking…' : healthStatus}
          </span>
        </p>
      </section>

      <section className="panel" aria-labelledby="open-run-heading">
        <h2 id="open-run-heading">Open run by ID</h2>
        <form className="inline-form" onSubmit={handleOpenRun}>
          <label>
            Run ID
            <input
              value={runId}
              onChange={(e) => setRunId(e.target.value)}
              placeholder="paste run_id"
              autoComplete="off"
            />
          </label>
          <button type="submit" disabled={!runId.trim()}>
            Open
          </button>
        </form>
      </section>

      <RecentRuns />

      <section className="panel" aria-labelledby="targets-preview-heading">
        <div className="section-header">
          <h2 id="targets-preview-heading">Targets</h2>
          <Link to="/targets">View all targets</Link>
        </div>
        {targets.isLoading && <p className="muted">Loading targets…</p>}
        {targets.isError && (
          <p className="banner error">Could not load targets.</p>
        )}
        {!targets.isLoading && !targets.isError && preview.length === 0 && (
          <p className="muted">No targets yet. Create one on the Targets page.</p>
        )}
        {preview.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Base URL</th>
                <th>Environment</th>
              </tr>
            </thead>
            <tbody>
              {preview.map((t) => (
                <tr key={t.name}>
                  <td>{t.name}</td>
                  <td>{t.base_url}</td>
                  <td>{t.environment ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="panel" aria-labelledby="demo-heading">
        <h2 id="demo-heading">Demo mode</h2>
        <DemoModeToggle />
      </section>
    </main>
  );
}
