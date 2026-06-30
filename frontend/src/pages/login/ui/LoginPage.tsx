import { Navigate } from 'react-router-dom';
import { authApi } from '@shared/api';
import { LoginForm } from '@features/auth-login';

export const LoginPage = () => {
  if (authApi.isAuthenticated()) {
    return <Navigate to="/admin" replace />;
  }

  return <LoginForm />;
};
