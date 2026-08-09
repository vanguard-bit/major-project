import { useEffect, useMemo, useState } from 'react';
import { useLiveEvidence } from './useApiHooks';
import type { LiveEvidenceRow, LivePlanKind, LiveProvider } from '../types/api';
import { RESULTS_MATRIX } from '../lib/livePlanDefaults';
import {
  latestByPlanId,
  newestRunId,
  planIdFor,
} from '../lib/liveEvidence';

function shortRunId(runId: string): string {
  if (runId.length <= 28) return runId;
  return `${runId.slice(0, 18)}…${runId.slice(-6)}`;
}

function riskClass(risk: number): string {
  if (risk >= 50) return 'risk-badge high';
  if (risk > 0) return 'risk-badge mid';
  return 'risk-badge clean';
}

function providerLabel(provider: LiveProvider): string {
  if (provider === 'github') return 'GitHub';
  if (provider === 'google') return 'Google';
  return 'Notion';
}

const PLAN_COLUMNS: LivePlanKind[] = ['readonly', 'smoke', 'smoke-extended'];
const PROVIDERS: LiveProvider[] = ['github', 'google', 'notion'];

type MatrixCell = {
  provider: LiveProvider;
  plan: LivePlanKind;
  planId: string;
  row: LiveEvidenceRow | null;
};

type Props = {
  screenshotMode?: boolean;
  onScreenshotModeChange?: (value: boolean) => void;
  showChromeControls?: boolean;
  /** After a fresh probe, focus this plan cell. */
  focusPlanId?: string | null;
};

export function LiveResultsBoard({
  screenshotMode = false,
  showChromeControls = true,
  focusPlanId = null,
}: Props) {
  const evidence = useLiveEvidence(true);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);

  const cells: MatrixCell[] = useMemo(() => {
    const byPlan = latestByPlanId(evidence.data ?? []);
    return RESULTS_MATRIX.map(({ provider, plan }) => {
      const id = planIdFor(provider, plan);
      return { provider, plan, planId: id, row: byPlan.get(id) ?? null };
    });
  }, [evidence.data]);

  const cellByPlan = useMemo(() => {
    const map = new Map<string, MatrixCell>();
    for (const cell of cells) map.set(cell.planId, cell);
    return map;
  }, [cells]);

  useEffect(() => {
    if (focusPlanId) setSelectedPlanId(focusPlanId);
  }, [focusPlanId]);

  useEffect(() => {
    setSelectedPlanId((current) => {
      if (current && cellByPlan.has(current)) return current;
      const newest = newestRunId(
        cells.map((c) => c.row).filter((r): r is LiveEvidenceRow => !!r),
      );
      if (!newest) return cells[0]?.planId ?? null;
      const match = cells.find((c) => c.row?.run_id === newest);
      return match?.planId ?? cells[0]?.planId ?? null;
    });
  }, [cells, cellByPlan]);

  const selected = selectedPlanId ? cellByPlan.get(selectedPlanId) ?? null : null;
  const completed = cells.filter((c) => c.row).length;

  return (
    <div className={screenshotMode ? 'results-board screenshot-mode' : 'results-board'}>
      <header className="results-header">
        <div>
          <p className="results-kicker">Adversarial Integration Tester</p>
          <h2 className="results-title" id="live-results-heading">
            Live probe results
          </h2>
          <p className="muted results-subtitle">
            Completed sandbox probes · {completed}/9 plans with artifacts
            {evidence.isFetching && !evidence.isLoading ? ' · refreshing…' : ''}
          </p>
          {showChromeControls && !screenshotMode && (
            <p className="muted field-help">
              Use <strong>Screenshot mode</strong> in the top bar to show the summary table for
              slides.
            </p>
          )}
        </div>
      </header>

      {evidence.isLoading && <p className="muted">Loading results…</p>}
      {evidence.isError && (
        <p className="banner error">
          Could not load live results. Coordinator needs <code>AIT_DEMO_LIVE_PROBES=1</code>.
        </p>
      )}

      {!evidence.isLoading && !evidence.isError && (
        <>
          <section className="panel" aria-labelledby="matrix-heading">
            <h3 id="matrix-heading">Risk matrix</h3>
            {!screenshotMode && (
              <p className="muted field-help">
                Click a cell to open that plan’s detail below. Only the latest run per plan is
                shown. <strong>readonly</strong> means the probe stays inside a narrow
                allowlist (expect a clean risk score when credentials work).
              </p>
            )}
            <table className="risk-matrix" data-testid="live-risk-matrix">
              <thead>
                <tr>
                  <th scope="col">Platform</th>
                  {PLAN_COLUMNS.map((plan) => (
                    <th key={plan} scope="col">
                      {plan}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {PROVIDERS.map((provider) => (
                  <tr key={provider}>
                    <th scope="row">{providerLabel(provider)}</th>
                    {PLAN_COLUMNS.map((plan) => {
                      const planId = planIdFor(provider, plan);
                      const cell = cellByPlan.get(planId);
                      const row = cell?.row ?? null;
                      const isSelected = selectedPlanId === planId;
                      return (
                        <td key={planId}>
                          <button
                            type="button"
                            className={
                              isSelected
                                ? 'matrix-cell selected'
                                : 'matrix-cell'
                            }
                            data-testid={`matrix-cell-${planId}`}
                            onClick={() => setSelectedPlanId(planId)}
                          >
                            {row ? (
                              <span className={riskClass(row.risk_score)}>
                                {row.risk_score}
                              </span>
                            ) : (
                              <span className="muted">—</span>
                            )}
                          </button>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          {screenshotMode && (
            <section className="panel results-summary" aria-labelledby="summary-heading">
              <h3 id="summary-heading">Summary</h3>
              <table className="results-table" data-testid="live-results-table">
                <thead>
                  <tr>
                    <th>Platform</th>
                    <th>Scenario</th>
                    <th>Risk</th>
                    <th>Result</th>
                    <th>Run identifier</th>
                  </tr>
                </thead>
                <tbody>
                  {cells.map((cell) => (
                    <tr key={cell.planId}>
                      <td>{providerLabel(cell.provider)}</td>
                      <td>{cell.plan}</td>
                      <td>
                        {cell.row ? (
                          <span className={riskClass(cell.row.risk_score)}>
                            {cell.row.risk_score}
                          </span>
                        ) : (
                          <span className="muted">—</span>
                        )}
                      </td>
                      <td>
                        {cell.row ? cell.row.result : <span className="muted">NOT RUN</span>}
                      </td>
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
          )}

          {!screenshotMode && (
          <section
            className="panel result-detail"
            aria-labelledby="detail-heading"
            data-testid="live-result-detail"
          >
            <h3 id="detail-heading">
              {selected
                ? `${providerLabel(selected.provider)} · ${selected.plan}`
                : 'Plan detail'}
            </h3>
            {!selected && <p className="muted">Select a matrix cell.</p>}
            {selected && !selected.row && (
              <p className="muted">
                No completed artifact for <code>{selected.planId}</code> yet.
              </p>
            )}
            {selected?.row && (
              <>
                <p className="result-card-meta">
                  <code>{selected.row.run_id}</code>
                  {' · '}
                  <span className={riskClass(selected.row.risk_score)}>
                    Risk {selected.row.risk_score}
                  </span>
                </p>
                <dl className="result-dl">
                  <div>
                    <dt>Result</dt>
                    <dd>{selected.row.result}</dd>
                  </div>
                  <div>
                    <dt>Hidden endpoints</dt>
                    <dd>
                      {selected.row.hidden_endpoints.length > 0 ? (
                        <ul className="endpoint-list hidden-response-list">
                          {selected.row.hidden_endpoints.map((ep) => {
                            const resp = (
                              selected.row?.hidden_endpoint_responses ?? []
                            ).find((r) => r.path === ep);
                            return (
                              <li key={ep} data-testid="hidden-endpoint-response">
                                <code>{ep}</code>
                                {resp ? (
                                  <div className="hidden-response-detail">
                                    <p className="muted">
                                      Observed response:{' '}
                                      {resp.status_code
                                        ? `HTTP ${resp.status_code}`
                                        : 'status unknown'}
                                      {resp.response_bytes
                                        ? ` · ${resp.response_bytes} bytes`
                                        : ''}
                                      {resp.content_type
                                        ? ` · ${resp.content_type}`
                                        : ''}
                                    </p>
                                    {resp.response_fields.length > 0 ? (
                                      <>
                                        <p className="muted">
                                          JSON fields returned (full body is not stored):
                                        </p>
                                        <code className="response-fields">
                                          {resp.response_fields.join(', ')}
                                        </code>
                                      </>
                                    ) : (
                                      <p className="muted">
                                        No JSON fields extracted (empty or non-object body).
                                      </p>
                                    )}
                                  </div>
                                ) : (
                                  <p className="muted">
                                    No observed response summary attached for this path.
                                  </p>
                                )}
                              </li>
                            );
                          })}
                        </ul>
                      ) : (
                        <span className="muted">None</span>
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt>Reached endpoints</dt>
                    <dd>
                      {selected.row.reached_endpoints.length > 0 ? (
                        <ul className="endpoint-list">
                          {selected.row.reached_endpoints.map((ep) => (
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
                      {selected.row.findings.length > 0 ? (
                        <ol className="findings-list">
                          {selected.row.findings.map((f, i) => (
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
          </section>
          )}
        </>
      )}
    </div>
  );
}
