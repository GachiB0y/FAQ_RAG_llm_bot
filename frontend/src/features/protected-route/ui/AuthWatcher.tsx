import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@entities/auth';

export const AuthWatcher = () => {
  const navigate = useNavigate();
  const logout = useAuthStore((state) => state.logout);

  useEffect(() => {
    const handler = () => {
      logout();
      navigate('/login', { replace: true });
    };

    window.addEventListener('auth:unauthorized', handler);

    return () => {
      window.removeEventListener('auth:unauthorized', handler);
    };
  }, [navigate, logout]);

  return null;
};
