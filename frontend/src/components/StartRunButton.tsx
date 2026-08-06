import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useStartRun } from './useApiHooks';
import { useRecentRuns } from '../hooks/useRecentRuns';

type Props = {
  targetName: string;
};

export function StartRunButton({ targetName }: Props) {
  const navigate = useNavigate();
  const { mutateAsync, isPending } = useStartRun();
  const { add } = useRecentRuns();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [toastRunId, setToastRunId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleConfirm() {
    setError(null);
    try {
      const data = await mutateAsync({ target_name: targetName });
      add({
        runId: data.run_id,
        startedAt: new Date().toISOString(),
        targetName,
      });
      setConfirmOpen(false);
      setToastRunId(data.run_id);
      navigate(`/runs/${data.run_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start run');
    }
  }

  return (
    <>
      <button type="button" disabled={isPending} onClick={() => setConfirmOpen(true)}>
        Start run
      </button>

      {confirmOpen && (
        <div className="modal-backdrop" role="presentation" onClick={() => setConfirmOpen(false)}>
          <div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="start-run-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="start-run-title">Start run for target &ldquo;{targetName}&rdquo;?</h2>
            {error && <p className="banner error">{error}</p>}
            <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
              <button type="button" disabled={isPending} onClick={handleConfirm}>
                Confirm
              </button>
              <button
                type="button"
                className="secondary"
                disabled={isPending}
                onClick={() => setConfirmOpen(false)}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {toastRunId && (
        <div className="banner success" role="status">
          Run started: <code>{toastRunId}</code>{' '}
          <Link to={`/runs/${toastRunId}`}>View run</Link>{' '}
          <button
            type="button"
            className="secondary"
            onClick={() => navigator.clipboard.writeText(toastRunId)}
          >
            Copy run id
          </button>
        </div>
      )}
    </>
  );
}
