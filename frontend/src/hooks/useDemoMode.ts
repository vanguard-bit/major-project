import { useCallback, useState } from 'react';

const KEY = 'ait.demoMode';

function envDefault(): boolean {
  return String(import.meta.env.VITE_DEMO_MODE ?? 'false').toLowerCase() === 'true';
}

function read(): boolean {
  const stored = localStorage.getItem(KEY);
  if (stored === null) return envDefault();
  return stored === 'true';
}

export function useDemoMode() {
  const [enabled, setEnabledState] = useState<boolean>(() => read());

  const setEnabled = useCallback((value: boolean) => {
    localStorage.setItem(KEY, String(value));
    setEnabledState(value);
  }, []);

  return { enabled, setEnabled };
}
