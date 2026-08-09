import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { defaultsFromBaseUrl } from '../lib/createTargetDefaults';
import { mapValidationErrorsToForm } from '../lib/mapValidationErrors';
import type { TargetConfig, TokenConfig } from '../types/api';
import { useCreateTarget } from './useApiHooks';

function isHttpUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch {
    return false;
  }
}

const httpUrlSchema = z
  .string()
  .min(1, 'Required')
  .refine(isHttpUrl, { message: 'Must be a valid http:// or https:// URL' });

const formSchema = z.object({
  name: z.string().min(1, 'Required'),
  environment: z.enum(['demo', 'sandbox', 'prod']),
  base_url: httpUrlSchema,
  integration_sync_url: httpUrlSchema,
  audit_base_url: httpUrlSchema,
  auth_type: z.enum(['static_token', 'oauth_client_credentials']),
  token: z.string(),
  token_url: z.string(),
  client_id: z.string(),
  client_secret: z.string(),
  scope: z.string(),
  openapi_paths: z.string(),
  seed_endpoints: z.string(),
  expected_endpoints: z.string(),
  expected_scopes: z.string(),
  sensitive_markers: z.string(),
  description: z.string(),
});

type FormValues = z.infer<typeof formSchema>;

const DEFAULT_VALUES: FormValues = {
  name: '',
  environment: 'demo',
  base_url: '',
  integration_sync_url: '',
  audit_base_url: '',
  auth_type: 'static_token',
  token: '',
  token_url: '',
  client_id: '',
  client_secret: '',
  scope: '',
  openapi_paths: '',
  seed_endpoints: '',
  expected_endpoints: '',
  expected_scopes: '',
  sensitive_markers: '',
  description: '',
};

function linesToArray(text: string): string[] | undefined {
  const items = text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
  return items.length > 0 ? items : undefined;
}

function csvToArray(text: string): string[] | undefined {
  const items = text
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean);
  return items.length > 0 ? items : undefined;
}

function buildPayload(values: FormValues): TargetConfig {
  const payload: TargetConfig = {
    name: values.name,
    environment: values.environment,
    base_url: values.base_url,
    integration_sync_url: values.integration_sync_url,
    audit_base_url: values.audit_base_url,
  };

  const tokenConfig: TokenConfig = {};
  if (values.token.trim()) tokenConfig.token = values.token.trim();
  if (values.token_url.trim()) tokenConfig.token_url = values.token_url.trim();
  if (values.client_id.trim()) tokenConfig.client_id = values.client_id.trim();
  if (values.client_secret.trim()) tokenConfig.client_secret = values.client_secret.trim();
  if (values.scope.trim()) tokenConfig.scope = values.scope.trim();

  const hasTokenConfig = Object.keys(tokenConfig).length > 0;
  if (values.auth_type !== 'static_token' || hasTokenConfig) {
    payload.auth_type = values.auth_type;
  }
  if (hasTokenConfig) {
    payload.token_config = tokenConfig;
  }

  const openapi_paths = linesToArray(values.openapi_paths);
  const seed_endpoints = linesToArray(values.seed_endpoints);
  const expected_endpoints = linesToArray(values.expected_endpoints);
  const expected_scopes = csvToArray(values.expected_scopes);
  const sensitive_markers = csvToArray(values.sensitive_markers);

  if (openapi_paths) payload.openapi_paths = openapi_paths;
  if (seed_endpoints) payload.seed_endpoints = seed_endpoints;
  if (expected_endpoints) payload.expected_endpoints = expected_endpoints;
  if (expected_scopes) payload.expected_scopes = expected_scopes;
  if (sensitive_markers) payload.sensitive_markers = sensitive_markers;
  if (values.description.trim()) payload.description = values.description.trim();

  return payload;
}

const FIELD_FOCUS_ORDER: (keyof FormValues)[] = [
  'name',
  'environment',
  'base_url',
  'integration_sync_url',
  'audit_base_url',
  'auth_type',
  'token',
  'token_url',
  'client_id',
  'client_secret',
  'scope',
  'openapi_paths',
  'seed_endpoints',
  'expected_endpoints',
  'expected_scopes',
  'sensitive_markers',
  'description',
];

export function CreateTargetForm() {
  const { mutateAsync, isPending } = useCreateTarget();
  const [integrationSyncPristine, setIntegrationSyncPristine] = useState(true);
  const [auditBasePristine, setAuditBasePristine] = useState(true);
  const [showSecret, setShowSecret] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    setValue,
    getValues,
    setError,
    setFocus,
    watch,
    formState: { errors },
    reset,
  } = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: DEFAULT_VALUES,
    shouldFocusError: true,
  });

  const watchedBaseUrl = watch('base_url');

  function applyDefaultsFromBase(baseUrl: string) {
    const defaults = defaultsFromBaseUrl(baseUrl);
    if (!defaults) return;
    if (integrationSyncPristine) {
      setValue('integration_sync_url', defaults.integration_sync_url, { shouldDirty: false });
    }
    if (auditBasePristine) {
      setValue('audit_base_url', defaults.audit_base_url, { shouldDirty: false });
    }
  }

  function resetIntegrationSync() {
    const defaults = defaultsFromBaseUrl(getValues('base_url'));
    if (!defaults) return;
    setValue('integration_sync_url', defaults.integration_sync_url, { shouldValidate: true });
    setIntegrationSyncPristine(true);
  }

  function resetAuditBase() {
    const defaults = defaultsFromBaseUrl(getValues('base_url'));
    if (!defaults) return;
    setValue('audit_base_url', defaults.audit_base_url, { shouldValidate: true });
    setAuditBasePristine(true);
  }

  function focusFirstInvalid(fieldNames: string[]) {
    const first = FIELD_FOCUS_ORDER.find((name) => fieldNames.includes(name));
    if (first) setFocus(first);
  }

  async function onSubmit(values: FormValues) {
    setSubmitError(null);
    setSuccessMessage(null);
    try {
      const created = await mutateAsync(buildPayload(values));
      setSuccessMessage(`Target created: ${created.name}`);
      reset(DEFAULT_VALUES);
      setIntegrationSyncPristine(true);
      setAuditBasePristine(true);
      setShowSecret(false);
    } catch (err) {
      const mapped = mapValidationErrorsToForm(err);
      const keys = Object.keys(mapped);
      if (keys.length === 0) {
        setSubmitError(err instanceof Error ? err.message : 'Failed to create target');
        return;
      }
      if (mapped.non_field) {
        setSubmitError(mapped.non_field);
      }
      const formKeys: string[] = [];
      for (const [key, message] of Object.entries(mapped)) {
        if (key === 'non_field') continue;
        if (key in DEFAULT_VALUES) {
          setError(key as keyof FormValues, { type: 'server', message });
          formKeys.push(key);
        } else {
          setSubmitError((prev) => prev ?? `${key}: ${message}`);
        }
      }
      focusFirstInvalid(formKeys);
    }
  }

  const baseUrlHint =
    watchedBaseUrl.trim() !== '' && !isHttpUrl(watchedBaseUrl)
      ? 'Base URL must include http:// or https://'
      : null;

  return (
    <form onSubmit={handleSubmit(onSubmit, (invalid) => focusFirstInvalid(Object.keys(invalid)))}>
      <h2>Create target</h2>

      {successMessage && <p className="banner success">{successMessage}</p>}
      {submitError && <p className="banner error">{submitError}</p>}

      <label>
        name
        <input
          type="text"
          autoComplete="off"
          aria-invalid={errors.name ? true : undefined}
          {...register('name')}
        />
        {errors.name && <span role="alert">{errors.name.message}</span>}
      </label>

      <label>
        environment
        <select aria-invalid={errors.environment ? true : undefined} {...register('environment')}>
          <option value="demo">demo</option>
          <option value="sandbox">sandbox</option>
          <option value="prod">prod</option>
        </select>
        {errors.environment && <span role="alert">{errors.environment.message}</span>}
      </label>

      <label>
        base_url
        <input
          type="url"
          autoComplete="off"
          aria-invalid={errors.base_url ? true : undefined}
          {...register('base_url', {
            onChange: (e) => applyDefaultsFromBase(e.target.value),
            onBlur: (e) => applyDefaultsFromBase(e.target.value),
          })}
        />
        {baseUrlHint && <span role="status">{baseUrlHint}</span>}
        {errors.base_url && <span role="alert">{errors.base_url.message}</span>}
      </label>

      <label>
        integration_sync_url
        <input
          type="url"
          autoComplete="off"
          aria-invalid={errors.integration_sync_url ? true : undefined}
          {...register('integration_sync_url', {
            onChange: () => setIntegrationSyncPristine(false),
          })}
        />
        <span>Auto-filled from base URL — edit if different.</span>
        <button type="button" className="secondary" onClick={resetIntegrationSync}>
          Reset to default
        </button>
        {errors.integration_sync_url && (
          <span role="alert">{errors.integration_sync_url.message}</span>
        )}
      </label>

      <label>
        audit_base_url
        <input
          type="url"
          autoComplete="off"
          aria-invalid={errors.audit_base_url ? true : undefined}
          {...register('audit_base_url', {
            onChange: () => setAuditBasePristine(false),
          })}
        />
        <span>Auto-filled from base URL — edit if different.</span>
        <button type="button" className="secondary" onClick={resetAuditBase}>
          Reset to default
        </button>
        {errors.audit_base_url && <span role="alert">{errors.audit_base_url.message}</span>}
      </label>

      <details className="accordion">
        <summary>Advanced target settings (optional)</summary>
        <div className="accordion-body">
          <label>
            auth_type
            <select aria-invalid={errors.auth_type ? true : undefined} {...register('auth_type')}>
              <option value="static_token">static_token</option>
              <option value="oauth_client_credentials">oauth_client_credentials</option>
            </select>
            {errors.auth_type && <span role="alert">{errors.auth_type.message}</span>}
          </label>

          <label>
            token
            <input
              type="text"
              autoComplete="off"
              aria-invalid={errors.token ? true : undefined}
              {...register('token')}
            />
            {errors.token && <span role="alert">{errors.token.message}</span>}
          </label>

          <label>
            token_url
            <input
              type="url"
              autoComplete="off"
              aria-invalid={errors.token_url ? true : undefined}
              {...register('token_url')}
            />
            {errors.token_url && <span role="alert">{errors.token_url.message}</span>}
          </label>

          <label>
            client_id
            <input
              type="text"
              autoComplete="off"
              aria-invalid={errors.client_id ? true : undefined}
              {...register('client_id')}
            />
            {errors.client_id && <span role="alert">{errors.client_id.message}</span>}
          </label>

          <label>
            client_secret
            <input
              type={showSecret ? 'text' : 'password'}
              autoComplete="new-password"
              aria-invalid={errors.client_secret ? true : undefined}
              {...register('client_secret')}
            />
            <button type="button" className="secondary" onClick={() => setShowSecret((v) => !v)}>
              {showSecret ? 'Hide' : 'Show'}
            </button>
            <span>Sent to API only — not stored in the frontend.</span>
            {errors.client_secret && <span role="alert">{errors.client_secret.message}</span>}
          </label>

          <label>
            scope
            <input
              type="text"
              autoComplete="off"
              aria-invalid={errors.scope ? true : undefined}
              {...register('scope')}
            />
            {errors.scope && <span role="alert">{errors.scope.message}</span>}
          </label>

          <label>
            openapi_paths (one per line)
            <textarea
              rows={3}
              aria-invalid={errors.openapi_paths ? true : undefined}
              {...register('openapi_paths')}
            />
            {errors.openapi_paths && <span role="alert">{errors.openapi_paths.message}</span>}
          </label>

          <label>
            seed_endpoints (one per line)
            <textarea
              rows={3}
              aria-invalid={errors.seed_endpoints ? true : undefined}
              {...register('seed_endpoints')}
            />
            {errors.seed_endpoints && <span role="alert">{errors.seed_endpoints.message}</span>}
          </label>

          <label>
            expected_endpoints (one per line)
            <textarea
              rows={3}
              aria-invalid={errors.expected_endpoints ? true : undefined}
              {...register('expected_endpoints')}
            />
            {errors.expected_endpoints && (
              <span role="alert">{errors.expected_endpoints.message}</span>
            )}
          </label>

          <label>
            expected_scopes (comma-separated)
            <input
              type="text"
              autoComplete="off"
              aria-invalid={errors.expected_scopes ? true : undefined}
              {...register('expected_scopes')}
            />
            {errors.expected_scopes && <span role="alert">{errors.expected_scopes.message}</span>}
          </label>

          <label>
            sensitive_markers (comma-separated)
            <input
              type="text"
              autoComplete="off"
              aria-invalid={errors.sensitive_markers ? true : undefined}
              {...register('sensitive_markers')}
            />
            {errors.sensitive_markers && (
              <span role="alert">{errors.sensitive_markers.message}</span>
            )}
          </label>

          <label>
            description
            <textarea
              rows={3}
              aria-invalid={errors.description ? true : undefined}
              {...register('description')}
            />
            {errors.description && <span role="alert">{errors.description.message}</span>}
          </label>
        </div>
      </details>

      <button type="submit" disabled={isPending}>
        {isPending ? 'Creating…' : 'Create target'}
      </button>
    </form>
  );
}
