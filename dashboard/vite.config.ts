import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { mockApi } from './vite-plugins/mock-api';

export default defineConfig({
  plugins: [
    react(),
    mockApi(path.resolve(__dirname, './public/mocks')),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
  server: {
    port: 3000,
  },
});
