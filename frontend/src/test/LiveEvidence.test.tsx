import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { ExplainProvider } from '../components/ExplainContext';
import { Live } from '../pages/Live';

vi.mock('../components/useApiHooks', () => ({
  useLiveEvidence: () => ({
    isLoading: false,
    isError: false,
    data: [
      {
        platform: 'GitHub',
        scenario: 'smoke',
        risk_score: 50,
        result: 'hidden /user/orgs, /user/repos',
        run_id: 'run-1',
        plan_id: 'github-smoke',
        hidden_endpoints: ['/user/orgs', '/user/repos'],
        reached_endpoints: ['/user', '/user/orgs', '/user/repos'],
        findings: [],
      },
    ],
  }),
  useLiveProbe: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
    data: undefined,
    error: null,
  }),
}));

function wrap(ui: JSX.Element) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ExplainProvider>
        <MemoryRouter>{ui}</MemoryRouter>
      </ExplainProvider>
    </QueryClientProvider>,
  );
}

describe('Live evidence page', () => {
  it('renders prior-run evidence and results board', () => {
    wrap(<Live />);
    expect(screen.getByTestId('live-evidence-table')).toBeInTheDocument();
    expect(screen.getByTestId('live-risk-matrix')).toBeInTheDocument();
    expect(screen.getByTestId('live-result-detail')).toBeInTheDocument();
    expect(screen.queryByTestId('live-results-table')).not.toBeInTheDocument();
    expect(screen.getAllByText('GitHub').length).toBeGreaterThan(0);
    expect(screen.getAllByText('50').length).toBeGreaterThan(0);
  });
});
