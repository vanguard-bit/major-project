import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { LiveResults } from '../pages/LiveResults';

vi.mock('../components/useApiHooks', () => ({
  useLiveEvidence: () => ({
    isLoading: false,
    isError: false,
    data: [
      {
        platform: 'GitHub',
        scenario: 'smoke-extended',
        risk_score: 100,
        result: 'hidden /user/orgs, /user/repos',
        run_id: 'github-smoke-extended-20260809T150323737157Z-c43aab77',
        plan_id: 'github-smoke-extended',
        hidden_endpoints: ['/user/orgs', '/user/repos'],
        reached_endpoints: ['/user', '/user/orgs', '/user/repos'],
        findings: [
          {
            severity: 'medium',
            category: 'hidden_endpoint',
            endpoint: '/user/orgs',
            title: 'Hidden endpoint access detected',
            evidence: 'x',
            expected_behavior: 'y',
            observed_behavior: 'z',
          },
        ],
      },
      {
        platform: 'Google',
        scenario: 'smoke',
        risk_score: 25,
        result: 'hidden /v1/projects',
        run_id: 'google-smoke-20260727T075516032903Z-4d0a5a31',
        plan_id: 'google-smoke',
        hidden_endpoints: ['/v1/projects'],
        reached_endpoints: ['/oauth2/v2/userinfo', '/v1/projects'],
        findings: [],
      },
    ],
  }),
}));

function wrap(ui: JSX.Element) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('LiveResults', () => {
  it('renders fixed 3×3 summary table and detail cards', () => {
    wrap(<LiveResults />);
    expect(screen.getByTestId('live-results-table')).toBeInTheDocument();
    expect(screen.getByText('Live SaaS probe results')).toBeInTheDocument();
    expect(screen.getByText(/\/9 completed sandbox probes/)).toBeInTheDocument();
    expect(screen.getByText(/2\/9 completed/)).toBeInTheDocument();
    // Always 9 cards in the matrix
    expect(screen.getAllByTestId('live-result-card').length).toBe(9);
    expect(screen.getByText(/Hidden endpoint access detected/)).toBeInTheDocument();
    expect(screen.getAllByText('NOT RUN').length).toBeGreaterThan(0);
  });
});
