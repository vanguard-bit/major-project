import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ExplainPanel } from '../components/ExplainPanel';
import { useExplainChromeOptional } from '../components/ExplainContext';
import { LiveProbeForm } from '../components/LiveProbeForm';
import { LiveResultsBoard } from '../components/LiveResultsBoard';
import { useLiveEvidence } from '../components/useApiHooks';
import {
  LIVE_ADVANCED,
  LIVE_PROBE_FORM,
  LIVE_RESULTS,
  LIVE_TRANSITION,
} from '../lib/liveExplainCopy';
import type { LiveEvidenceRow, LiveProbeResponse } from '../types/api';

export function Live() {
  const evidence = useLiveEvidence(true);
  const { screenshotMode, setScreenshotMode } = useExplainChromeOptional();
  const [selected, setSelected] = useState<LiveEvidenceRow | null>(null);
  const [focusPlanId, setFocusPlanId] = useState<string | null>(null);
  const rows = evidence.data ?? [];

  function handleProbeResult(result: LiveProbeResponse) {
    setFocusPlanId(result.plan_id);
    document.getElementById('results')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  return (
    <main
      className={
        screenshotMode ? 'act-page live-page screenshot-mode' : 'act-page live-page'
      }
    >
      {!screenshotMode && (
        <>
          <p className="act-pill" data-testid="act-pill">
            Act 2 · Live
          </p>

          <section className="story-block" aria-labelledby="transition-heading">
            <h1 id="transition-heading">From demo to live software-as-a-service</h1>
            <ExplainPanel
              lead={LIVE_TRANSITION.lead}
              sections={LIVE_TRANSITION.sections}
            />
          </section>

          <section className="story-block" aria-labelledby="probe-heading">
            <h2 id="probe-heading">Run a live probe</h2>
            <ExplainPanel
              lead={LIVE_PROBE_FORM.lead}
              sections={LIVE_PROBE_FORM.sections}
            />
            <LiveProbeForm onResult={handleProbeResult} />
          </section>
        </>
      )}

      <section
        className="story-block"
        id="results"
        aria-labelledby="live-results-heading"
      >
        {!screenshotMode && (
          <>
            <h2 className="sr-only">Live probe results</h2>
            <ExplainPanel lead={LIVE_RESULTS.lead} sections={LIVE_RESULTS.sections} />
          </>
        )}
        <LiveResultsBoard
          screenshotMode={screenshotMode}
          onScreenshotModeChange={setScreenshotMode}
          showChromeControls={!screenshotMode}
          focusPlanId={focusPlanId}
        />
      </section>

      {!screenshotMode && (
        <details className="advanced-block">
          <summary>Advanced · prior runs</summary>
          <ExplainPanel lead={LIVE_ADVANCED.lead} sections={LIVE_ADVANCED.sections} />

          <section className="panel" aria-labelledby="evidence-heading">
            <h3 id="evidence-heading">Prior runs</h3>
            <p className="muted field-help">
              Full history. The board above shows only the latest run per plan.
            </p>
            {evidence.isLoading && <p className="muted">Loading evidence…</p>}
            {evidence.isError && (
              <p className="banner error">
                Could not load live evidence. Is the coordinator running with{' '}
                <code>AIT_DEMO_LIVE_PROBES=1</code>?
              </p>
            )}
            {!evidence.isLoading && !evidence.isError && rows.length === 0 && (
              <p className="muted">No completed live artifacts found under results/derived.</p>
            )}
            {rows.length > 0 && (
              <table data-testid="live-evidence-table">
                <thead>
                  <tr>
                    <th>Platform</th>
                    <th>Scenario</th>
                    <th>Risk</th>
                    <th>Result</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr
                      key={row.run_id}
                      className={selected?.run_id === row.run_id ? 'selected' : undefined}
                      onClick={() => setSelected(row)}
                      style={{ cursor: 'pointer' }}
                    >
                      <td>{row.platform}</td>
                      <td>{row.scenario}</td>
                      <td>{row.risk_score}</td>
                      <td>{row.result}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {selected && (
              <div className="panel nested" data-testid="live-evidence-detail">
                <h4>
                  {selected.platform} / {selected.scenario}
                </h4>
                <p>
                  <strong>Run identifier:</strong> {selected.run_id}
                </p>
                <p>
                  <strong>Hidden:</strong>{' '}
                  {selected.hidden_endpoints.join(', ') || 'none'}
                </p>
                <p>
                  <strong>Reached:</strong>{' '}
                  {selected.reached_endpoints.join(', ') || 'none'}
                </p>
                {selected.findings.length > 0 && (
                  <ol>
                    {selected.findings.map((f, i) => (
                      <li key={`${f.endpoint}-${i}`}>
                        <strong>{f.severity?.toUpperCase?.() ?? f.severity}</strong>{' '}
                        {f.title} — <code>{f.endpoint}</code>
                      </li>
                    ))}
                  </ol>
                )}
              </div>
            )}
          </section>

          <p className="muted">
            Still need the mock walkthrough? <Link to="/demo">Back to Demo</Link>
          </p>
        </details>
      )}
    </main>
  );
}
