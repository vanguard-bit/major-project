import { NavLink, Route, Routes } from 'react-router-dom';
import { Dashboard } from './pages/Dashboard';
import { Live } from './pages/Live';
import { RunDetail } from './pages/RunDetail';
import { Targets } from './pages/Targets';

export default function App() {
  return (
    <>
      <nav>
        <NavLink to="/" end>
          Dashboard
        </NavLink>
        <NavLink to="/targets">Targets</NavLink>
        <NavLink to="/live">Live</NavLink>
      </nav>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/targets" element={<Targets />} />
        <Route path="/live" element={<Live />} />
        <Route path="/runs/:id" element={<RunDetail />} />
      </Routes>
    </>
  );
}
