import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import InvestigationsPage from './pages/InvestigationsPage';
import WorkspacePage from './pages/WorkspacePage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/investigations" replace />} />
        <Route path="/investigations" element={<InvestigationsPage />} />
        <Route path="/investigations/:id" element={<WorkspacePage />} />
        {/* catch-all */}
        <Route path="*" element={<Navigate to="/investigations" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
