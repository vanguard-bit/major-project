import { NavLink, Route, Routes } from 'react-router-dom';
import { Dashboard } from './pages/Dashboard';
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
      </nav>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/targets" element={<Targets />} />
        <Route path="/runs/:id" element={<RunDetail />} />
      </Routes>
    </>
  );
}
