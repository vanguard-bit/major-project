import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useLiveEvidence } from '../components/useApiHooks';
import type { LiveEvidenceRow } from '../types/api';

function shortRunId(runId: string): string {
  if (runId.length <= 28) return runId;
  return `${runId.slice(0, 18)}…${runId.slice(-6)}`;
}

function riskClass(risk: number): string {
  if (risk >= 50) return 'risk-badge high';
  if (risk > 0) return 'risk-badge mid';
  return 'risk-badge clean';
}

/** Prefer newest row per plan_id so slides are not flooded with retries. */
function latestPerPlan(rows: LiveEvidenceRow[]): LiveEvidenceRow[] {
  const seen = new Set<string>();
  const out: LiveEvidenceRow[] = [];
  // API returns sorted by filename; re-sort by run_id timestamp when present
  const sorted = [...rows].sort((a, b) => b.run_id.localeCompare(a.run_id));
  for (const row of sorted) {
    if (seen.has(row.plan_id)) continue;
    seen.add(row.plan_id);
    out.push(row);
  }
  return out;
}

export function LiveResults() {
  const evidence = useLiveEvidence(true);
  const [screenshotMode, setScreenshotMode] = useState(false);
  const [latestOnly, setLatestOnly] = useState(true);

  const rows = useMemo(() => {
    const raw = evidence.data ?? [];
    return latestOnly ? latestPerPlan(raw) : [...raw].sort((a, b) => b.run_id.localeCompare(a.run_id));
  }, [evidence.data, latestOnly]);

  return (
    <main className={screenshotMode ? 'results-main screenshot-mode' : 'results-main'}>
      {!screenshotMode && (
        <p className="banner info">
          Presentation board for live probes. Turn on <strong>Screenshot mode</strong> before
          capturing slides. <Link to="/live">Back to Live</Link>
        </p>
      )}

      <header className="results-header">
        <div>
          <p className="results-kicker">Adversarial Integration Tester</p>
          <h1>Live SaaS probe results</h1>
          <p className="muted results-subtitle">
            Policy allowlist vs observed traffic · completed sandbox probes
          </p>
        </div>
        {!screenshotMode && (
          <div className="results-controls">
            <label className="demo-mode-toggle">
              <input
                type="checkbox"
                checked={latestOnly}
                onChange={(e) => setLatestOnly(e.target.checked)}
              />
              Latest per plan
            </label>
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
      {!evidence.isLoading && !evidence.isError && rows.length === 0 && (
        <p className="muted">No completed live runs yet. Run a probe on the Live page first.</p>
      )}

      {rows.length > 0 && (
        <>
          <section className="panel results-summary" aria-labelledby="summary-heading">
            <h2 id="summary-heading">Summary</h2>
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
                {rows.map((row) => (
                  <tr key={row.run_id}>
                    <td>{row.platform}</td>
                    <td>{row.scenario}</td>
                    <td>
                      <span className={riskClass(row.risk_score)}>{row.risk_score}</span>
                    </td>
                    <td>{row.result}</td>
                    <td>
                      <code className="run-id" title={row.run_id}>
                        {shortRunId(row.run_id)}
                      </code>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="panel" aria-labelledby="detail-heading">
            <h2 id="detail-heading">Findings detail</h2>
            <div className="results-grid">
              {rows.map((row) => (
                <article key={row.run_id} className="result-card" data-testid="live-result-card">
                  <header className="result-card-header">
                    <h3>
                      {row.platform} · {row.scenario}
                    </h3>
                    <span className={riskClass(row.risk_score)}>Risk {row.risk_score}</span>
                  </header>
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
                </article>
              ))}
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
