import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { StartRunButton } from '../components/StartRunButton';

const mutateAsync = vi.fn();
const add = vi.fn();
const navigate = vi.fn();

vi.mock('../components/useApiHooks', () => ({
  useStartRun: () => ({ mutateAsync, isPending: false }),
}));

vi.mock('../hooks/useRecentRuns', () => ({
  useRecentRuns: () => ({ add, entries: [], remove: vi.fn(), clear: vi.fn() }),
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => navigate };
});

describe('StartRunButton', () => {
  beforeEach(() => {
    mutateAsync.mockReset();
    add.mockReset();
    navigate.mockReset();
    vi.spyOn(window, 'alert').mockImplementation(() => {});
    mutateAsync.mockResolvedValue({
      run_id: 'run-123',
      status: 'completed',
      target: { name: 'demo-integration' },
      config: {},
      findings: [],
      exchanges: [],
    });
  });

  it('starts a run after confirm and records recent run', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <StartRunButton targetName="demo-integration" />
      </MemoryRouter>,
    );
    await user.click(screen.getByRole('button', { name: /start run/i }));
    await user.click(screen.getByRole('button', { name: /confirm/i }));
    expect(mutateAsync).toHaveBeenCalledWith({ target_name: 'demo-integration' });
    expect(add).toHaveBeenCalledWith(
      expect.objectContaining({ runId: 'run-123', targetName: 'demo-integration' }),
    );
    expect(window.alert).toHaveBeenCalledWith('Run started: run-123');
    expect(navigate).toHaveBeenCalledWith('/runs/run-123');
  });
});
