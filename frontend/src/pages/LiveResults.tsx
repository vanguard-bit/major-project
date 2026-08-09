import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useLiveEvidence } from '../components/useApiHooks';
import type { LiveEvidenceRow, LivePlanKind, LiveProvider } from '../types/api';
import { RESULTS_MATRIX } from '../lib/livePlanDefaults';

function shortRunId(runId: string): string {
  if (runId.length <= 28) return runId;
  return `${runId.slice(0, 18)}…${runId.slice(-6)}`;
}

function riskClass(risk: number): string {
  if (risk >= 50) return 'risk-badge high';
  if (risk > 0) return 'risk-badge mid';
  return 'risk-badge clean';
}

function planIdFor(provider: LiveProvider, plan: LivePlanKind): string {
  return `${provider}-${plan}`;
}

function latestByPlanId(rows: LiveEvidenceRow[]): Map<string, LiveEvidenceRow> {
  const sorted = [...rows].sort((a, b) => b.run_id.localeCompare(a.run_id));
  const map = new Map<string, LiveEvidenceRow>();
  for (const row of sorted) {
    if (!map.has(row.plan_id)) map.set(row.plan_id, row);
  }
  return map;
}

type MatrixCell = {
  provider: LiveProvider;
  plan: LivePlanKind;
  planId: string;
  row: LiveEvidenceRow | null;
};

export function LiveResults() {
  const evidence = useLiveEvidence(true);
  const [screenshotMode, setScreenshotMode] = useState(false);

  const cells: MatrixCell[] = useMemo(() => {
    const byPlan = latestByPlanId(evidence.data ?? []);
    return RESULTS_MATRIX.map(({ provider, plan }) => {
      const id = planIdFor(provider, plan);
      return { provider, plan, planId: id, row: byPlan.get(id) ?? null };
    });
  }, [evidence.data]);

  const completed = cells.filter((c) => c.row).length;

  return (
    <main className={screenshotMode ? 'results-main screenshot-mode' : 'results-main'}>
      {!screenshotMode && (
        <p className="banner info">
          3×3 live matrix (GitHub / Google / Notion × readonly / smoke / smoke-extended). Turn on{' '}
          <strong>Screenshot mode</strong> before capturing slides.{' '}
          <Link to="/live">Back to Live</Link>
        </p>
      )}

      <header className="results-header">
        <div>
          <p className="results-kicker">Adversarial Integration Tester</p>
          <h1>Live SaaS probe results</h1>
          <p className="muted results-subtitle">
            Policy allowlist vs observed traffic · {completed}/9 completed sandbox probes
          </p>
        </div>
        {!screenshotMode && (
          <div className="results-controls">
            <label className="demo-mode-toggle">
              <input
                type="checkbox"
                checked={screenshotMode}
                onChange={(e) => setScreenshotMode(e.target.checked)}
                data-testid="screenshot-mode-toggle"
              />
              Screenshot mode
            </label>
          </div>
        )}
      </header>

      {evidence.isLoading && <p className="muted">Loading results…</p>}
      {evidence.isError && (
        <p className="banner error">
          Could not load live results. Coordinator needs <code>AIT_DEMO_LIVE_PROBES=1</code>.
        </p>
      )}

      {!evidence.isLoading && !evidence.isError && (
        <>
          <section className="panel results-summary" aria-labelledby="summary-heading">
            <h2 id="summary-heading">Summary (3×3)</h2>
            <table className="results-table" data-testid="live-results-table">
              <thead>
                <tr>
                  <th>Platform</th>
                  <th>Scenario</th>
                  <th>Risk</th>
                  <th>Result</th>
                  <th>Run ID</th>
                </tr>
              </thead>
              <tbody>
                {cells.map((cell) => (
                  <tr key={cell.planId}>
                    <td>{cell.provider === 'github' ? 'GitHub' : cell.provider === 'google' ? 'Google' : 'Notion'}</td>
                    <td>{cell.plan}</td>
                    <td>
                      {cell.row ? (
                        <span className={riskClass(cell.row.risk_score)}>{cell.row.risk_score}</span>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                    <td>{cell.row ? cell.row.result : <span className="muted">NOT RUN</span>}</td>
                    <td>
                      {cell.row ? (
                        <code className="run-id" title={cell.row.run_id}>
                          {shortRunId(cell.row.run_id)}
                        </code>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="panel" aria-labelledby="detail-heading">
            <h2 id="detail-heading">Findings detail</h2>
            <div className="results-grid">
              {cells.map((cell) => {
                const row = cell.row;
                const title = `${cell.provider === 'github' ? 'GitHub' : cell.provider === 'google' ? 'Google' : 'Notion'} · ${cell.plan}`;
                return (
                  <article key={cell.planId} className="result-card" data-testid="live-result-card">
                    <header className="result-card-header">
                      <h3>{title}</h3>
                      {row ? (
                        <span className={riskClass(row.risk_score)}>Risk {row.risk_score}</span>
                      ) : (
                        <span className="muted">NOT RUN</span>
                      )}
                    </header>
                    {!row && (
                      <p className="muted">No completed artifact for {cell.planId} yet.</p>
                    )}
                    {row && (
                      <>
                        <p className="result-card-meta">
                          <code>{row.run_id}</code>
                        </p>
                        <dl className="result-dl">
                          <div>
                            <dt>Result</dt>
                            <dd>{row.result}</dd>
                          </div>
                          <div>
                            <dt>Hidden endpoints</dt>
                            <dd>
                              {row.hidden_endpoints.length > 0 ? (
                                <ul className="endpoint-list">
                                  {row.hidden_endpoints.map((ep) => (
                                    <li key={ep}>
                                      <code>{ep}</code>
                                    </li>
                                  ))}
                                </ul>
                              ) : (
                                <span className="muted">None</span>
                              )}
                            </dd>
                          </div>
                          <div>
                            <dt>Reached endpoints</dt>
                            <dd>
                              {row.reached_endpoints.length > 0 ? (
                                <ul className="endpoint-list">
                                  {row.reached_endpoints.map((ep) => (
                                    <li key={ep}>
                                      <code>{ep}</code>
                                    </li>
                                  ))}
                                </ul>
                              ) : (
                                <span className="muted">None</span>
                              )}
                            </dd>
                          </div>
                          <div>
                            <dt>Findings</dt>
                            <dd>
                              {row.findings.length > 0 ? (
                                <ol className="findings-list">
                                  {row.findings.map((f, i) => (
                                    <li key={`${f.endpoint}-${i}`}>
                                      <strong>
                                        {(f.severity ?? '').toString().toUpperCase() || 'FINDING'}
                                      </strong>{' '}
                                      {f.title}
                                      {f.endpoint ? (
                                        <>
                                          {' '}
                                          — <code>{f.endpoint}</code>
                                        </>
                                      ) : null}
                                    </li>
                                  ))}
                                </ol>
                              ) : (
                                <span className="muted">No findings (clean)</span>
                              )}
                            </dd>
                          </div>
                        </dl>
                      </>
                    )}
                  </article>
                );
              })}
            </div>
          </section>
        </>
      )}

      {screenshotMode && (
        <button
          type="button"
          className="screenshot-exit"
          onClick={() => setScreenshotMode(false)}
        >
          Exit screenshot mode
        </button>
      )}
    </main>
  );
}
