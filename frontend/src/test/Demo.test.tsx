import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { ExplainProvider } from '../components/ExplainContext';
import { Demo } from '../pages/Demo';

vi.mock('../components/useApiHooks', () => ({
  useHealth: () => ({ isLoading: false, isError: false, data: { status: 'ok' } }),
  useTargets: () => ({
    isLoading: false,
    isError: false,
    data: [
      {
        name: 'demo-integration',
        base_url: 'http://127.0.0.1:8002',
        environment: 'demo',
      },
    ],
  }),
  useStartRun: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useCreateTarget: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

vi.mock('../components/RecentRuns', () => ({
  RecentRuns: () => <div data-testid="recent-runs-stub">Recent runs</div>,
}));

vi.mock('../components/CreateTargetForm', () => ({
  CreateTargetForm: () => <div data-testid="create-target-stub" />,
}));

vi.mock('../components/DemoModeToggle', () => ({
  DemoModeToggle: () => <label>Demo mode</label>,
}));

vi.mock('../components/StartRunButton', () => ({
  StartRunButton: ({ label }: { label?: string }) => (
    <button type="button">{label ?? 'Start run'}</button>
  ),
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

describe('Demo page', () => {
  it('renders two-act story sections and continue link', () => {
    wrap(<Demo />);
    expect(screen.getByTestId('act-pill')).toHaveTextContent(/Act 1/);
    expect(screen.getByText('Why this exists')).toBeInTheDocument();
    expect(screen.getByText('This act')).toBeInTheDocument();
    expect(screen.getByText('Policy in play')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Start demo assessment' }),
    ).toBeInTheDocument();
    expect(screen.getByTestId('continue-to-live')).toHaveAttribute('href', '/live');
    expect(screen.getByTestId('policy-snapshot')).toBeInTheDocument();
  });
});
