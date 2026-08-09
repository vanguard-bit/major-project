import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

type ExplainContextValue = {
  hideAll: boolean;
  setHideAll: (value: boolean) => void;
  screenshotMode: boolean;
  setScreenshotMode: (value: boolean) => void;
};

const ExplainContext = createContext<ExplainContextValue | null>(null);

export function ExplainProvider({ children }: { children: ReactNode }) {
  const [hideAll, setHideAll] = useState(false);
  const [screenshotMode, setScreenshotMode] = useState(false);

  const value = useMemo(
    () => ({
      hideAll,
      setHideAll,
      screenshotMode,
      setScreenshotMode,
    }),
    [hideAll, screenshotMode],
  );

  return <ExplainContext.Provider value={value}>{children}</ExplainContext.Provider>;
}

export function useExplainChrome() {
  const ctx = useContext(ExplainContext);
  if (!ctx) {
    throw new Error('useExplainChrome must be used within ExplainProvider');
  }
  return ctx;
}

/** Safe for components that may render outside the provider (tests). */
export function useExplainChromeOptional(): ExplainContextValue {
  const ctx = useContext(ExplainContext);
  const noop = useCallback((_value: boolean) => {}, []);
  return (
    ctx ?? {
      hideAll: false,
      setHideAll: noop,
      screenshotMode: false,
      setScreenshotMode: noop,
    }
  );
}
