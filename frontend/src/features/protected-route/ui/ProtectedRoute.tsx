import { Navigate, Outlet } from 'react-router-dom';
import { authApi } from '@shared/api';

export const ProtectedRoute = () => {
  const isAuthenticated = authApi.isAuthenticated();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
};
