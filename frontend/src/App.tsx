import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import InvestigationsPage from './pages/InvestigationsPage';
import WorkspacePage from './pages/WorkspacePage';

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-gray-50 text-gray-900">
        <Routes>
          <Route path="/investigations" element={<InvestigationsPage />} />
          <Route path="/investigations/:id" element={<WorkspacePage />} />
          <Route path="*" element={<Navigate to="/investigations" replace />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
