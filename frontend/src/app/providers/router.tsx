import { createBrowserRouter, Navigate } from 'react-router-dom';
import { AdminLayout } from '@app/layouts';
import { ProtectedRoute } from '@features/protected-route';
import { ChatPage } from '@pages/chat';
import { DocumentsPage } from '@pages/documents';
import { LoginPage } from '@pages/login';
import { SettingsPage } from '@pages/settings';
import { UsersPage } from '@pages/users';

export const appRouter = createBrowserRouter([
  // Public routes
  {
    path: '/login',
    element: <LoginPage />,
  },
  // Root redirects to admin
  {
    path: '/',
    element: <Navigate to="/admin" replace />,
  },
  // Protected admin routes
  {
    path: '/admin',
    element: <ProtectedRoute />,
    children: [
      {
        element: <AdminLayout />,
        children: [
          {
            index: true,
            element: <Navigate to="/admin/chat" replace />,
          },
          {
            path: 'chat',
            element: <ChatPage />,
          },
          {
            path: 'documents',
            element: <DocumentsPage />,
          },
          {
            path: 'users',
            element: <UsersPage />,
          },
          {
            path: 'settings',
            element: <SettingsPage />,
          },
        ],
      },
    ],
  },
]);
