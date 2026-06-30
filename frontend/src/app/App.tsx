import { RouterProvider } from 'react-router-dom';

import { appRouter } from './providers/router';

export const App = () => <RouterProvider router={appRouter} />;
