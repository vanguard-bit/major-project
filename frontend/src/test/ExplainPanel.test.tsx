import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ExplainPanel } from '../components/ExplainPanel';
import { ExplainProvider } from '../components/ExplainContext';

const sections = {
  what: 'What body',
  why: 'Why body',
  whatAitDoes: 'AIT body',
};

describe('ExplainPanel', () => {
  it('shows a single explanation box and Hide removes it', async () => {
    const user = userEvent.setup();
    render(
      <ExplainProvider>
        <ExplainPanel lead="Lead sentence." sections={sections} />
      </ExplainProvider>,
    );

    expect(screen.getByTestId('explain-body')).toBeInTheDocument();
    expect(screen.getByText('Lead sentence.')).toBeInTheDocument();
    expect(screen.getByText('What body')).toBeInTheDocument();
    expect(screen.queryByText(/How to read/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/If asked/i)).not.toBeInTheDocument();

    await user.click(screen.getByTestId('explain-toggle'));
    expect(screen.queryByTestId('explain-body')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Show explanation' })).toBeInTheDocument();
  });
});
