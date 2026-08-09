import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { RunDetail } from '../pages/RunDetail';

vi.mock('../hooks/useDemoMode', () => ({
  useDemoMode: () => ({ enabled: false, setEnabled: vi.fn() }),
}));

vi.mock('../components/useApiHooks', () => ({
  useRun: () => ({
    isLoading: false,
    isError: false,
    dataUpdatedAt: Date.now(),
    failureCount: 0,
    refetch: vi.fn(),
    data: {
      run_id: 'run-demo-1',
      status: 'completed',
      target: {
        name: 'demo-integration',
        environment: 'demo',
        base_url: 'http://127.0.0.1:8001/',
        integration_sync_url: 'http://127.0.0.1:8002/sync',
        audit_base_url: 'http://127.0.0.1:8001/',
        auth_type: 'oauth_client_credentials',
        token_config: {
          scope: 'crm.read billing.read',
          client_secret: 'should-not-appear',
        },
        expected_endpoints: [
          '/api/v1/customers',
          '/api/v1/customers/cust-001',
          '/api/v1/customers/cust-001/notes',
        ],
        expected_scopes: ['crm.read'],
        sensitive_markers: ['billing_email', 'tax_id'],
      },
      config: { safety_mode: true },
      findings: [],
      exchanges: [],
      report: {
        run_id: 'run-demo-1',
        target_name: 'demo-integration',
        status: 'completed',
        risk_score: 75,
        reached_endpoints: ['/api/v1/customers', '/billing'],
        hidden_endpoints: ['/billing'],
        sensitive_fields_accessed: ['billing_email'],
        divergence_summary: ['undeclared billing'],
        findings: [
          {
            severity: 'high',
            category: 'hidden_endpoint',
            endpoint: '/billing',
            title: 'Hidden endpoint access detected',
            evidence: 'x',
            expected_behavior: 'y',
            observed_behavior: 'Reached /billing outside allowlist',
          },
        ],
      },
    },
  }),
  useFindings: () => ({ isLoading: false, isError: false, data: [] }),
}));

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/runs/run-demo-1']}>
        <Routes>
          <Route path="/runs/:id" element={<RunDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('RunDetail', () => {
  it('shows inline report and main config without open-report button or secrets', () => {
    wrap();
    expect(screen.getByTestId('run-report')).toBeInTheDocument();
    expect(screen.getByTestId('report-risk')).toHaveTextContent('75');
    expect(screen.getAllByText('/billing').length).toBeGreaterThan(0);
    expect(screen.getByTestId('run-config')).toBeInTheDocument();
    expect(screen.getByText('Expected endpoints (allowlist)')).toBeInTheDocument();
    expect(screen.getByText('crm.read billing.read')).toBeInTheDocument();
    expect(screen.queryByText('should-not-appear')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /open report/i })).not.toBeInTheDocument();
  });
});
