import { Link, Route, Routes } from 'react-router-dom';

function Home() {
  return (
    <main>
      <h1>AIT Frontend</h1>
      <p>Adversarial Integration Tester — minimal SPA scaffold.</p>
    </main>
  );
}

export default function App() {
  return (
    <>
      <nav>
        <Link to="/">Dashboard</Link>
        <Link to="/targets">Targets</Link>
      </nav>
      <Routes>
        <Route path="/" element={<Home />} />
      </Routes>
    </>
  );
}
