import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/health': 'http://127.0.0.1:8000',
      '/metrics': 'http://127.0.0.1:8000',
      '/conversations': 'http://127.0.0.1:8000',
      '/docs': 'http://127.0.0.1:8000',
      '/chat': 'http://127.0.0.1:8000',
      '/retrieve': 'http://127.0.0.1:8000',
      '/ticket': 'http://127.0.0.1:8000',
    },
  },
  preview: {
    port: 8000,
    strictPort: true,
  },
});