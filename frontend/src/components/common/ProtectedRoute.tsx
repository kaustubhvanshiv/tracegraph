import { Navigate, Outlet } from 'react-router-dom';
import { tokenStore } from '../../services/authApi';

/**
 * Wraps any route that requires a valid JWT.
 * Redirects to /login if the user isn't logged in.
 */
export default function ProtectedRoute() {
  return tokenStore.isLoggedIn() ? <Outlet /> : <Navigate to="/login" replace />;
}
