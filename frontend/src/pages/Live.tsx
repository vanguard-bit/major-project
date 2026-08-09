import { useState } from 'react';
import { LiveProbeForm } from '../components/LiveProbeForm';
import { useLiveEvidence } from '../components/useApiHooks';
import type { LiveEvidenceRow } from '../types/api';

export function Live() {
  const evidence = useLiveEvidence(true);
  const [selected, setSelected] = useState<LiveEvidenceRow | null>(null);

  const rows = evidence.data ?? [];

  return (
    <main>
      <h1>Live SaaS evidence</h1>
      <p className="muted">
        Prior completed live probes (policy allowlist vs observed traffic). Run a new probe
        below with a pasted sandbox token.
      </p>

      <section className="panel" aria-labelledby="evidence-heading">
        <h2 id="evidence-heading">Prior runs</h2>
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
            <h3>
              {selected.platform} / {selected.scenario}
            </h3>
            <p>
              <strong>Run ID:</strong> {selected.run_id}
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
                    <strong>{f.severity?.toUpperCase?.() ?? f.severity}</strong> {f.title}{' '}
                    — <code>{f.endpoint}</code>
                  </li>
                ))}
              </ol>
            )}
          </div>
        )}
      </section>

      <LiveProbeForm />
    </main>
  );
}
