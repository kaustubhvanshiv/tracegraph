import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import ProtectedRoute from './components/common/ProtectedRoute';
import LoginPage from './pages/LoginPage';
import InvestigationsPage from './pages/InvestigationsPage';
import WorkspacePage from './pages/WorkspacePage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public */}
        <Route path="/login" element={<LoginPage />} />

        {/* Protected — require JWT */}
        <Route element={<ProtectedRoute />}>
          <Route path="/investigations" element={<InvestigationsPage />} />
          <Route path="/investigations/:id" element={<WorkspacePage />} />
        </Route>

        {/* Default redirect */}
        <Route path="/" element={<Navigate to="/investigations" replace />} />
        <Route path="*" element={<Navigate to="/investigations" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
