import { useEffect } from 'react';
import { useForm, useWatch } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { useLiveProbe } from './useApiHooks';
import type { LivePlanKind, LiveProbeResponse, LiveProvider } from '../types/api';
import {
  DEFAULT_PLAN,
  FIELD_HELP,
  metaFor,
  plansForProvider,
} from '../lib/livePlanDefaults';

const schema = z.object({
  provider: z.enum(['github', 'google', 'notion']),
  plan: z.enum(['smoke', 'readonly', 'smoke-extended']),
  planFile: z.string().min(1),
  token: z.string().min(1, 'Paste a sandbox token'),
});

type FormValues = z.infer<typeof schema>;

type Props = {
  onResult?: (result: LiveProbeResponse) => void;
};

function syncPlanFields(
  provider: LiveProvider,
  plan: LivePlanKind,
  setValue: (name: keyof FormValues, value: string) => void,
) {
  const available = plansForProvider(provider);
  const chosen =
    available.find((p) => p.kind === plan)?.kind ?? DEFAULT_PLAN[provider];
  const meta = metaFor(provider, chosen);
  setValue('plan', chosen);
  setValue('planFile', meta?.path ?? '');
}

export function LiveProbeForm({ onResult }: Props) {
  const probe = useLiveProbe();
  const {
    register,
    handleSubmit,
    setValue,
    control,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      provider: 'github',
      plan: DEFAULT_PLAN.github,
      planFile: metaFor('github', DEFAULT_PLAN.github)?.path ?? '',
      token: '',
    },
  });

  const provider = useWatch({ control, name: 'provider' }) as LiveProvider;
  const plan = useWatch({ control, name: 'plan' }) as LivePlanKind;
  const planOptions = plansForProvider(provider);
  const planMeta = metaFor(provider, plan);

  useEffect(() => {
    syncPlanFields(provider, DEFAULT_PLAN[provider], setValue);
  }, [provider, setValue]);

  useEffect(() => {
    const meta = metaFor(provider, plan);
    if (meta) {
      setValue('planFile', meta.path);
    } else {
      syncPlanFields(provider, DEFAULT_PLAN[provider], setValue);
    }
  }, [provider, plan, setValue]);

  useEffect(() => {
    return () => {
      setValue('token', '');
    };
  }, [setValue]);

  async function onSubmit(values: FormValues) {
    probe.reset();
    try {
      const result = await probe.mutateAsync({
        provider: values.provider,
        plan: values.plan,
        token: values.token,
      });
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
    <section className="panel" aria-labelledby="live-probe-form-heading">
      <h3 id="live-probe-form-heading" className="sr-only">
        Probe form
      </h3>
      <form className="stack-form" onSubmit={handleSubmit(onSubmit)} autoComplete="off">
        <label>
          Provider
          <select {...register('provider')} data-testid="live-provider">
            <option value="github">GitHub</option>
            <option value="google">Google</option>
            <option value="notion">Notion</option>
          </select>
        </label>
        <p className="field-help">{FIELD_HELP.provider}</p>

        <label>
          Plan
          <select {...register('plan')} data-testid="live-plan">
            {planOptions.map((p) => (
              <option key={p.kind} value={p.kind}>
                {p.label}
              </option>
            ))}
          </select>
        </label>
        <p className="field-help">{planMeta?.description ?? FIELD_HELP.plan}</p>

        <label>
          Plan configuration file
          <input
            type="text"
            readOnly
            data-testid="live-plan-file"
            {...register('planFile')}
          />
        </label>
        <p className="field-help">{FIELD_HELP.planFile}</p>

        <label>
          Sandbox token
          <input
            type="password"
            autoComplete="off"
            data-testid="live-token-input"
            {...register('token')}
          />
        </label>
        <p className="field-help">{FIELD_HELP.token}</p>
        {errors.token && <p className="banner error">{errors.token.message}</p>}

        <button type="submit" disabled={isSubmitting || probe.isPending}>
          {probe.isPending ? 'Running…' : 'Run probe'}
        </button>
      </form>
      {errorMessage && <p className="banner error">{errorMessage}</p>}
      {result && (
        <p className="banner success" data-testid="live-probe-result">
          Latest probe <code>{result.plan_id}</code> · risk {result.risk_score} ·{' '}
          <code>{result.run_id}</code> — detail selected in results below (replaces the
          previous artifact for that plan).
        </p>
      )}
    </section>
  );
}
