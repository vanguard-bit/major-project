import { useCallback, useState } from 'react';
import type { RecentRunEntry } from '../types/api';

const KEY = 'ait.recentRuns';
const CAP = 10;

function read(): RecentRunEntry[] {
  try {
    const raw = sessionStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as RecentRunEntry[]) : [];
  } catch {
    return [];
  }
}

function write(list: RecentRunEntry[]) {
  sessionStorage.setItem(KEY, JSON.stringify(list));
}

export function useRecentRuns() {
  const [entries, setEntriesState] = useState<RecentRunEntry[]>(() => read());

  const setEntries = useCallback((list: RecentRunEntry[]) => {
    write(list);
    setEntriesState(list);
  }, []);

  const add = useCallback((entry: RecentRunEntry) => {
    const next = [entry, ...read().filter((r) => r.runId !== entry.runId)].slice(0, CAP);
    write(next);
    setEntriesState(next);
  }, []);

  const remove = useCallback((runId: string) => {
    const next = read().filter((r) => r.runId !== runId);
    write(next);
    setEntriesState(next);
  }, []);

  const clear = useCallback(() => {
    write([]);
    setEntriesState([]);
  }, []);

  return { entries, add, remove, clear, setEntries };
}
