import { Navigate } from 'react-router-dom';

/** Deep-link compatibility: Results board now lives on /live#results */
export function LiveResults() {
  return <Navigate to="/live#results" replace />;
}
