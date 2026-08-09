import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { ExplainProvider } from '../components/ExplainContext';
import { LiveResultsBoard } from '../components/LiveResultsBoard';

vi.mock('../components/useApiHooks', () => ({
  useLiveEvidence: () => ({
    isLoading: false,
    isError: false,
    isFetching: false,
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
        hidden_endpoint_responses: [
          {
            path: '/user/orgs',
            status_code: 200,
            response_bytes: 2,
            response_fields: [],
            content_type: 'application/json; charset=utf-8',
          },
          {
            path: '/user/repos',
            status_code: 200,
            response_bytes: 5373,
            response_fields: ['id', 'name', 'full_name', 'private', 'owner.login'],
            content_type: 'application/json; charset=utf-8',
          },
        ],
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
      <ExplainProvider>
        <MemoryRouter>{ui}</MemoryRouter>
      </ExplainProvider>
    </QueryClientProvider>,
  );
}

describe('LiveResultsBoard', () => {
  it('shows matrix + detail normally without summary table', async () => {
    const user = userEvent.setup();
    wrap(
      <LiveResultsBoard
        screenshotMode={false}
        showChromeControls
        focusPlanId="github-smoke-extended"
      />,
    );
    expect(screen.getByTestId('live-risk-matrix')).toBeInTheDocument();
    expect(screen.queryByTestId('live-results-table')).not.toBeInTheDocument();
    expect(screen.getByTestId('live-result-detail')).toBeInTheDocument();
    expect(
      screen.getByText(/means the probe stays inside a narrow allowlist/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/Hidden endpoint access detected/)).toBeInTheDocument();
    expect(screen.getByText(/JSON fields returned/i)).toBeInTheDocument();
    expect(screen.getByText(/owner\.login/)).toBeInTheDocument();

    await user.click(screen.getByTestId('matrix-cell-google-smoke'));
    const detail = screen.getByTestId('live-result-detail');
    expect(detail.querySelector('#detail-heading')).toHaveTextContent('Google · smoke');
  });

  it('shows summary table in screenshot mode for slides', () => {
    wrap(<LiveResultsBoard screenshotMode showChromeControls={false} />);
    expect(screen.getByTestId('live-results-table')).toBeInTheDocument();
    expect(screen.queryByTestId('live-result-detail')).not.toBeInTheDocument();
  });
});
