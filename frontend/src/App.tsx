import { NavLink, Route, Routes } from 'react-router-dom';
import { Dashboard } from './pages/Dashboard';
import { Live } from './pages/Live';
import { LiveResults } from './pages/LiveResults';
import { RunDetail } from './pages/RunDetail';
import { Targets } from './pages/Targets';

export default function App() {
  return (
    <>
      <nav className="app-nav">
        <NavLink to="/" end>
          Dashboard
        </NavLink>
        <NavLink to="/targets">Targets</NavLink>
        <NavLink to="/live">Live</NavLink>
        <NavLink to="/live/results">Results</NavLink>
      </nav>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/targets" element={<Targets />} />
        <Route path="/live" element={<Live />} />
        <Route path="/live/results" element={<LiveResults />} />
        <Route path="/runs/:id" element={<RunDetail />} />
      </Routes>
    </>
  );
}
