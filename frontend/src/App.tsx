import { NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { ExplainProvider, useExplainChrome } from './components/ExplainContext';
import { Demo } from './pages/Demo';
import { Live } from './pages/Live';
import { LiveResults } from './pages/LiveResults';
import { RunDetail } from './pages/RunDetail';

function AppChrome() {
  const { hideAll, setHideAll, screenshotMode, setScreenshotMode } =
    useExplainChrome();
  const { pathname } = useLocation();
  const onLive = pathname === '/live' || pathname.startsWith('/live/');

  return (
    <>
      <nav className="app-nav" aria-label="Primary" data-testid="app-nav">
        <NavLink to="/demo" className="brand-link" end>
          AIT
        </NavLink>
        <NavLink to="/demo">Demo</NavLink>
        <NavLink to="/live">Live</NavLink>
        <div className="nav-controls">
          <label className="demo-mode-toggle">
            <input
              type="checkbox"
              checked={hideAll}
              onChange={(e) => setHideAll(e.target.checked)}
              data-testid="hide-all-explanations"
            />
            Hide explanations
          </label>
          {onLive && (
            <label className="demo-mode-toggle">
              <input
                type="checkbox"
                checked={screenshotMode}
                onChange={(e) => setScreenshotMode(e.target.checked)}
                data-testid="screenshot-mode-toggle"
              />
              Screenshot mode
            </label>
          )}
        </div>
      </nav>
      <Routes>
        <Route path="/" element={<Navigate to="/demo" replace />} />
        <Route path="/demo" element={<Demo />} />
        <Route path="/targets" element={<Navigate to="/demo#advanced" replace />} />
        <Route path="/live" element={<Live />} />
        <Route path="/live/results" element={<LiveResults />} />
        <Route path="/runs/:id" element={<RunDetail />} />
      </Routes>
    </>
  );
}

export default function App() {
  return (
    <ExplainProvider>
      <AppChrome />
    </ExplainProvider>
  );
}
