import path from 'node:path';

import { fileURLToPath } from 'node:url';

import react from '@vitejs/plugin-react-swc';
import { defineConfig } from 'vite';

const rootDir = path.dirname(fileURLToPath(import.meta.url));
const resolveFromRoot = (segment: string) => path.resolve(rootDir, segment);

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@app': resolveFromRoot('src/app'),
      '@pages': resolveFromRoot('src/pages'),
      '@widgets': resolveFromRoot('src/widgets'),
      '@features': resolveFromRoot('src/features'),
      '@entities': resolveFromRoot('src/entities'),
      '@shared': resolveFromRoot('src/shared'),
    },
  },
  server: {
    port: 5173,
    open: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
