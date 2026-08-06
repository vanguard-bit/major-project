import { useDemoMode } from '../hooks/useDemoMode';

export function DemoModeToggle() {
  const { enabled, setEnabled } = useDemoMode();

  return (
    <label className="demo-mode-toggle">
      <input
        type="checkbox"
        checked={enabled}
        onChange={(e) => setEnabled(e.target.checked)}
      />
      Demo mode
    </label>
  );
}
