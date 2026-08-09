import { Link } from 'react-router-dom';
import { CreateTargetForm } from '../components/CreateTargetForm';
import { StartRunButton } from '../components/StartRunButton';
import { useTargets } from '../components/useApiHooks';

export function Targets() {
  const { data, isLoading, isError } = useTargets();
  const targets = data ?? [];

  return (
    <main>
      <h1>Targets</h1>
      <p>
        <Link to="/">← Dashboard</Link>
      </p>

      <section className="panel" aria-labelledby="create-target-heading">
        <h2 id="create-target-heading">Create target</h2>
        <CreateTargetForm />
      </section>

      <section className="panel" aria-labelledby="targets-list-heading">
        <h2 id="targets-list-heading">All targets</h2>
        {isLoading && <p className="muted">Loading targets…</p>}
        {isError && <p className="banner error">Could not load targets.</p>}
        {!isLoading && !isError && targets.length === 0 && (
          <p className="muted">No targets configured yet.</p>
        )}
        {targets.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Base URL</th>
                <th>Environment</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {targets.map((t) => (
                <tr key={t.name}>
                  <td>{t.name}</td>
                  <td>{t.base_url}</td>
                  <td>{t.environment ?? '—'}</td>
                  <td>
                    <StartRunButton targetName={t.name} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}
