import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { LiveProbeForm } from '../components/LiveProbeForm';

const mutateAsync = vi.fn().mockResolvedValue({
  run_id: 'run-xyz',
  provider: 'github',
  plan_id: 'github-smoke-extended',
  status: 'completed',
  risk_score: 50,
  hidden_endpoints: ['/user/orgs'],
  reached_endpoints: ['/user', '/user/orgs'],
  findings: [],
});

vi.mock('../components/useApiHooks', () => ({
  useLiveProbe: () => ({
    mutateAsync,
    isPending: false,
    data: undefined,
    error: null,
    reset: vi.fn(),
  }),
}));

function wrap(ui: JSX.Element) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('LiveProbeForm', () => {
  beforeEach(() => {
    mutateAsync.mockClear();
    sessionStorage.clear();
    localStorage.clear();
  });

  it('submits probe and clears token; never stores token in browser storage', async () => {
    const user = userEvent.setup();
    wrap(<LiveProbeForm />);
    const input = screen.getByTestId('live-token-input') as HTMLInputElement;
    expect((screen.getByTestId('live-plan-file') as HTMLInputElement).value).toContain('github_smoke_extended.yaml');
    await user.selectOptions(screen.getByTestId('live-provider'), 'notion');
    expect((screen.getByTestId('live-plan-file') as HTMLInputElement).value).toContain('notion_smoke_extended.yaml');
    await user.selectOptions(screen.getByTestId('live-provider'), 'github');
    await user.type(input, 'super-secret-token');
    await user.click(screen.getByRole('button', { name: /run probe/i }));
    await waitFor(() => expect(mutateAsync).toHaveBeenCalled());
    expect(mutateAsync.mock.calls[0][0].token).toBe('super-secret-token');
    await waitFor(() => expect(input.value).toBe(''));
    expect(sessionStorage.getItem('ait.liveToken')).toBeNull();
    expect(localStorage.getItem('ait.liveToken')).toBeNull();
    const blob = JSON.stringify({ ...sessionStorage, ...localStorage });
    expect(blob).not.toContain('super-secret-token');
  });
});
