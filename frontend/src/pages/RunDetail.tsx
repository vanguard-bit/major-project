import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { useFindings, useRun } from '../components/useApiHooks';
import { useDemoMode } from '../hooks/useDemoMode';
import type { RunReport, TargetConfig, TestRunConfig } from '../types/api';
import { TERMINAL_RUN_STATUSES } from '../types/api';

const MAX_POLL_MS = 5 * 60 * 1000;

function riskClass(risk: number): string {
  if (risk >= 50) return 'risk-badge high';
  if (risk > 0) return 'risk-badge mid';
  return 'risk-badge clean';
}

function listOrNone(items: string[] | undefined) {
  if (!items || items.length === 0) return <span className="muted">None</span>;
  return (
    <ul className="endpoint-list">
      {items.map((item) => (
        <li key={item}>
          <code>{item}</code>
        </li>
      ))}
    </ul>
  );
}

function DemoConfigSnapshot({
  target,
  config,
}: {
  target: TargetConfig;
  config: TestRunConfig;
}) {
  return (
    <section className="panel" aria-labelledby="config-heading" data-testid="run-config">
      <h2 id="config-heading">Run config</h2>
      <p className="muted">Main policy settings for this assessment (secrets omitted).</p>
      <dl className="result-dl config-dl">
        <div>
          <dt>Target</dt>
          <dd>
            <code>{target.name}</code>
            {target.environment ? ` · ${target.environment}` : ''}
          </dd>
        </div>
        <div>
          <dt>Base URL</dt>
          <dd>
            <code>{target.base_url}</code>
          </dd>
        </div>
        <div>
          <dt>Integration sync</dt>
          <dd>
            <code>{target.integration_sync_url}</code>
          </dd>
        </div>
        <div>
          <dt>Expected endpoints (allowlist)</dt>
          <dd>{listOrNone(target.expected_endpoints)}</dd>
        </div>
        <div>
          <dt>Expected scopes</dt>
          <dd>{listOrNone(target.expected_scopes)}</dd>
        </div>
        <div>
          <dt>Sensitive markers</dt>
          <dd>{listOrNone(target.sensitive_markers)}</dd>
        </div>
        <div>
          <dt>Auth</dt>
          <dd>
            {target.auth_type ?? '—'}
            {target.token_config?.scope ? (
              <>
                {' · scope '}
                <code>{target.token_config.scope}</code>
              </>
            ) : null}
          </dd>
        </div>
        <div>
          <dt>Safety mode</dt>
          <dd>{config.safety_mode === false ? 'off' : 'on'}</dd>
        </div>
      </dl>
    </section>
  );
}

function InlineReport({ report }: { report: RunReport }) {
  return (
    <section className="panel report-panel" aria-labelledby="report-heading" data-testid="run-report">
      <h2 id="report-heading">Report</h2>
      <div className="report-summary">
        <p>
          <strong>Risk score:</strong>{' '}
          <span className={riskClass(report.risk_score)} data-testid="report-risk">
            {report.risk_score}
          </span>
        </p>
        <p>
          <strong>Status:</strong> {report.status}
        </p>
        <p>
          <strong>Target:</strong> <code>{report.target_name}</code>
        </p>
      </div>

      <div className="report-grid">
        <div>
          <h3>Hidden endpoints</h3>
          {listOrNone(report.hidden_endpoints)}
        </div>
        <div>
          <h3>Reached endpoints</h3>
          {listOrNone(report.reached_endpoints)}
        </div>
        <div>
          <h3>Sensitive fields accessed</h3>
          {listOrNone(report.sensitive_fields_accessed)}
        </div>
        <div>
          <h3>Divergence summary</h3>
          {listOrNone(report.divergence_summary)}
        </div>
      </div>

      <h3>Findings detail</h3>
      {report.findings.length === 0 ? (
        <p className="muted">No findings (clean).</p>
      ) : (
        <ol className="findings-list report-findings" data-testid="report-findings">
          {report.findings.map((f, i) => (
            <li key={`${f.endpoint}-${f.title}-${i}`}>
              <strong>{(f.severity ?? '').toString().toUpperCase()}</strong> {f.title}
              {f.endpoint ? (
                <>
                  {' '}
                  — <code>{f.endpoint}</code>
                </>
              ) : null}
              {f.observed_behavior ? <p className="muted">{f.observed_behavior}</p> : null}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

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
  const report = run?.report ?? null;

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

  if (!id) {
    return (
      <main>
        <p className="banner error">Missing run identifier.</p>
        <Link to="/demo">Back to Demo</Link>
      </main>
    );
  }

  return (
    <main className="act-page run-detail-page">
      <p>
        <Link to="/demo">← Demo</Link>
      </p>
      <h1>Run {id}</h1>

      {runQuery.isLoading && <p className="muted">Loading run…</p>}
      {runQuery.isError && (
        <p className="banner error">Could not load run. Check the identifier and try again.</p>
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
              Still waiting — refresh manually{' '}
              <button type="button" className="secondary" onClick={() => runQuery.refetch()}>
                Refresh
              </button>
            </p>
          )}
        </section>
      )}

      {run?.target && run.config && (
        <DemoConfigSnapshot target={run.target} config={run.config} />
      )}

      {report ? (
        <InlineReport report={report} />
      ) : (
        run &&
        isTerminal && (
          <p className="banner info">Run finished but no report payload was attached.</p>
        )
      )}

      {!report && (
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
      )}

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
              Open mock software-as-a-service audit for {id}
            </a>
          </p>
        </section>
      )}
    </main>
  );
}
