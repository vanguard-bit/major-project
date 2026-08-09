import { FormEvent, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { CreateTargetForm } from '../components/CreateTargetForm';
import { DemoModeToggle } from '../components/DemoModeToggle';
import { ExplainPanel } from '../components/ExplainPanel';
import { RecentRuns } from '../components/RecentRuns';
import { StartRunButton } from '../components/StartRunButton';
import { useHealth, useTargets } from '../components/useApiHooks';
import {
  DEMO_ADVANCED,
  DEMO_NEXT,
  DEMO_OUTCOME,
  DEMO_POLICY,
  DEMO_THIS_ACT,
  DEMO_WHY,
} from '../lib/demoExplainCopy';

const DEMO_TARGET = 'demo-integration';

export function Demo() {
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

  const demoTarget = (targets.data ?? []).find((t) => t.name === DEMO_TARGET);
  const preview = (targets.data ?? []).slice(0, 5);

  return (
    <main className="act-page demo-page">
      <p className="act-pill" data-testid="act-pill">
        Act 1 · Demo
      </p>

      <section className="story-block" aria-labelledby="why-heading">
        <h1 id="why-heading">Why this exists</h1>
        <ExplainPanel lead={DEMO_WHY.lead} sections={DEMO_WHY.sections} />
        <p className="health-inline">
          Coordinator:{' '}
          <span className={healthClass} data-testid="health-badge">
            {health.isLoading ? 'checking…' : healthStatus}
          </span>
        </p>
      </section>

      <section className="story-block" aria-labelledby="this-act-heading">
        <h2 id="this-act-heading">This act</h2>
        <ExplainPanel lead={DEMO_THIS_ACT.lead} sections={DEMO_THIS_ACT.sections} />
        <ul className="story-list">
          <li>
            Mock customer relationship management system and demo integration (local stack via{' '}
            <code>npm run dev</code>)
          </li>
          <li>
            Seeded target <code>{DEMO_TARGET}</code>
          </li>
          <li>No software-as-a-service tokens required</li>
        </ul>
      </section>

      <section className="story-block" aria-labelledby="policy-heading">
        <h2 id="policy-heading">Policy in play</h2>
        <ExplainPanel lead={DEMO_POLICY.lead} sections={DEMO_POLICY.sections} />
        <div className="policy-snapshot" data-testid="policy-snapshot">
          <p>
            <strong>Target:</strong>{' '}
            {demoTarget ? (
              <>
                <code>{demoTarget.name}</code> · {demoTarget.base_url}
              </>
            ) : targets.isLoading ? (
              <span className="muted">Loading…</span>
            ) : (
              <span className="muted">
                <code>{DEMO_TARGET}</code> (seed when coordinator starts)
              </span>
            )}
          </p>
          <p className="muted">
            Declared allowlist covers customer relationship management sync paths. Undeclared
            billing traffic is the rehearsed finding.
          </p>
        </div>
      </section>

      <section className="story-block story-cta" aria-labelledby="start-heading">
        <h2 id="start-heading">Start demo assessment</h2>
        <p className="explain-lead">
          Runs the seeded <code>{DEMO_TARGET}</code> assessment and opens the run detail
          page.
        </p>
        <StartRunButton targetName={DEMO_TARGET} label="Start demo assessment" />
      </section>

      <section className="story-block" aria-labelledby="outcome-heading">
        <h2 id="outcome-heading">Outcome</h2>
        <ExplainPanel lead={DEMO_OUTCOME.lead} sections={DEMO_OUTCOME.sections} />
        <RecentRuns />
      </section>

      <section className="story-block next-block" aria-labelledby="next-heading">
        <h2 id="next-heading">Next</h2>
        <ExplainPanel lead={DEMO_NEXT.lead} sections={DEMO_NEXT.sections} />
        <Link className="primary-link" to="/live" data-testid="continue-to-live">
          Continue to Live →
        </Link>
      </section>

      <details className="advanced-block" id="advanced">
        <summary>Advanced</summary>
        <ExplainPanel lead={DEMO_ADVANCED.lead} sections={DEMO_ADVANCED.sections} />

        <section className="panel" aria-labelledby="create-target-heading">
          <h3 id="create-target-heading">Create target</h3>
          <CreateTargetForm />
        </section>

        <section className="panel" aria-labelledby="targets-list-heading">
          <h3 id="targets-list-heading">Targets</h3>
          {targets.isLoading && <p className="muted">Loading targets…</p>}
          {targets.isError && <p className="banner error">Could not load targets.</p>}
          {!targets.isLoading && !targets.isError && preview.length === 0 && (
            <p className="muted">No targets yet.</p>
          )}
          {preview.length > 0 && (
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Base URL</th>
                  <th>Environment</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {(targets.data ?? []).map((t) => (
                  <tr key={t.name}>
                    <td>{t.name}</td>
                    <td>{t.base_url}</td>
                    <td>{t.environment ?? '—'}</td>
                    <td>
                      <StartRunButton targetName={t.name} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="panel" aria-labelledby="open-run-heading">
          <h3 id="open-run-heading">Open run by identifier</h3>
          <form className="inline-form" onSubmit={handleOpenRun}>
            <label>
              Run identifier
              <input
                value={runId}
                onChange={(e) => setRunId(e.target.value)}
                placeholder="paste run identifier"
                autoComplete="off"
              />
            </label>
            <button type="submit" disabled={!runId.trim()}>
              Open
            </button>
          </form>
        </section>

        <section className="panel" aria-labelledby="demo-mode-heading">
          <h3 id="demo-mode-heading">Demo mode</h3>
          <DemoModeToggle />
        </section>
      </details>
    </main>
  );
}
