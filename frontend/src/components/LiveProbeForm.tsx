import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { useLiveProbe } from './useApiHooks';
import type { LiveProbeResponse } from '../types/api';

const schema = z.object({
  provider: z.enum(['github', 'google']),
  plan: z.enum(['smoke', 'readonly', 'smoke-extended']),
  token: z.string().min(1, 'Paste a sandbox token'),
});

type FormValues = z.infer<typeof schema>;

type Props = {
  onResult?: (result: LiveProbeResponse) => void;
};

export function LiveProbeForm({ onResult }: Props) {
  const probe = useLiveProbe();
  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      provider: 'github',
      plan: 'smoke-extended',
      token: '',
    },
  });

  useEffect(() => {
    return () => {
      setValue('token', '');
    };
  }, [setValue]);

  async function onSubmit(values: FormValues) {
    try {
      const result = await probe.mutateAsync(values);
      onResult?.(result);
    } finally {
      setValue('token', '');
    }
  }

  const result = probe.data;
  const errorMessage =
    probe.error &&
    (probe.error as { response?: { data?: { detail?: string } }; message?: string })
      .response?.data?.detail
      ? String(
          (probe.error as { response?: { data?: { detail?: string } } }).response?.data
            ?.detail,
        )
      : probe.error
        ? 'Live probe failed'
        : null;

  return (
    <section className="panel" aria-labelledby="live-probe-heading">
      <h2 id="live-probe-heading">Run live probe</h2>
      <p className="muted">
        Paste a sandbox token. It is sent only to localhost for this request and is cleared
        afterward — never stored in browser storage.
      </p>
      <form className="stack-form" onSubmit={handleSubmit(onSubmit)} autoComplete="off">
        <label>
          Provider
          <select {...register('provider')}>
            <option value="github">GitHub</option>
            <option value="google">Google</option>
          </select>
        </label>
        <label>
          Plan
          <select {...register('plan')}>
            <option value="smoke-extended">smoke-extended (API-doc GETs)</option>
            <option value="smoke">smoke</option>
            <option value="readonly">readonly</option>
          </select>
        </label>
        <label>
          Sandbox token
          <input
            type="password"
            autoComplete="off"
            data-testid="live-token-input"
            {...register('token')}
          />
        </label>
        {errors.token && <p className="banner error">{errors.token.message}</p>}
        <button type="submit" disabled={isSubmitting || probe.isPending}>
          {probe.isPending ? 'Running…' : 'Run probe'}
        </button>
      </form>
      {errorMessage && <p className="banner error">{errorMessage}</p>}
      {result && (
        <div className="panel nested" data-testid="live-probe-result">
          <h3>Probe result</h3>
          <p>
            <strong>Run ID:</strong> {result.run_id}
          </p>
          <p>
            <strong>Risk:</strong> {result.risk_score}
          </p>
          <p>
            <strong>Hidden endpoints:</strong>{' '}
            {result.hidden_endpoints.length
              ? result.hidden_endpoints.join(', ')
              : 'none'}
          </p>
          <p>
            <strong>Reached:</strong> {result.reached_endpoints.join(', ') || 'none'}
          </p>
          {result.findings.length > 0 && (
            <ol>
              {result.findings.map((f, i) => (
                <li key={`${f.endpoint}-${i}`}>
                  <strong>{f.severity.toUpperCase()}</strong> {f.title} —{' '}
                  <code>{f.endpoint}</code>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </section>
  );
}
