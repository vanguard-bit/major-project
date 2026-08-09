import { useEffect, useRef } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './ApiClient';
import type {
  Finding,
  LiveEvidenceRow,
  LiveProbeRequest,
  LiveProbeResponse,
  RunRecord,
  TargetConfig,
} from '../types/api';
import { TERMINAL_RUN_STATUSES } from '../types/api';

const POLL_MS = 3000;
const MAX_POLL_MS = 5 * 60 * 1000;

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => api.get('/health').then((r) => r.data as { status: string }),
    staleTime: 30_000,
  });
}

export function useTargets() {
  return useQuery({
    queryKey: ['targets'],
    queryFn: () => api.get('/targets').then((r) => r.data as TargetConfig[]),
    staleTime: 60_000,
  });
}

export function useCreateTarget() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: TargetConfig) =>
      api.post('/targets', payload).then((r) => r.data as TargetConfig),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['targets'] }),
  });
}

export function useStartRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { target_name: string; config?: Record<string, unknown> }) =>
      api.post('/runs', payload).then((r) => r.data as RunRecord),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['targets'] }),
  });
}

export function useRun(runId: string, enabled = true) {
  const pollStartedAt = useRef(Date.now());
  useEffect(() => {
    pollStartedAt.current = Date.now();
  }, [runId]);
  return useQuery({
    queryKey: ['run', runId],
    queryFn: () => api.get(`/runs/${runId}`).then((r) => r.data as RunRecord),
    enabled: enabled && !!runId,
    staleTime: 3000,
    retry: 2,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data && TERMINAL_RUN_STATUSES.has(data.status)) return false;
      const elapsed = Date.now() - pollStartedAt.current;
      if (elapsed > MAX_POLL_MS) return false;
      if (query.state.fetchFailureCount >= 5) return 30_000;
      return POLL_MS;
    },
  });
}

export function useFindings(runId: string) {
  return useQuery({
    queryKey: ['findings', runId],
    queryFn: () => api.get(`/runs/${runId}/findings`).then((r) => r.data as Finding[]),
    enabled: !!runId,
    staleTime: 5000,
  });
}


export function useLiveEvidence(enabled = true) {
  return useQuery({
    queryKey: ['live-evidence'],
    queryFn: () => api.get('/live/evidence').then((r) => r.data as LiveEvidenceRow[]),
    enabled,
    staleTime: 30_000,
    retry: 1,
  });
}

export function useLiveProbe() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: LiveProbeRequest) =>
      api
        .post('/live/probes', payload, { timeout: 60_000 })
        .then((r) => r.data as LiveProbeResponse),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['live-evidence'] }),
  });
}
