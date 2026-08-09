import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CreateTargetForm } from '../components/CreateTargetForm';

vi.mock('../components/useApiHooks', () => ({
  useCreateTarget: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

function renderForm() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <CreateTargetForm />
    </QueryClientProvider>,
  );
}

describe('CreateTargetForm pristine auto-fill', () => {
  it('auto-fills from base_url, preserves edited sync URL, and reset restores default', async () => {
    const user = userEvent.setup();
    renderForm();

    const baseUrlInput = screen.getByLabelText('base_url');
    const syncUrlInput = screen.getByLabelText(/^integration_sync_url/);
    const auditUrlInput = screen.getByLabelText(/^audit_base_url/);

    await user.type(baseUrlInput, 'http://127.0.0.1:8001/');
    expect(syncUrlInput).toHaveValue('http://127.0.0.1:8001/sync');
    expect(auditUrlInput).toHaveValue('http://127.0.0.1:8001');

    await user.clear(syncUrlInput);
    await user.type(syncUrlInput, 'http://custom.example/sync');
    expect(syncUrlInput).toHaveValue('http://custom.example/sync');

    await user.clear(baseUrlInput);
    await user.type(baseUrlInput, 'http://127.0.0.1:9000/');
    expect(syncUrlInput).toHaveValue('http://custom.example/sync');
    expect(auditUrlInput).toHaveValue('http://127.0.0.1:9000');

    const [syncResetButton] = screen.getAllByRole('button', { name: /Reset to default/i });
    await user.click(syncResetButton);
    expect(syncUrlInput).toHaveValue('http://127.0.0.1:9000/sync');
  });
});
