import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// In development the React app calls /api and /media on its own origin and Vite
// forwards them to Django, so no CORS setup is needed while developing.
const DJANGO = process.env.DJANGO_URL || 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: DJANGO, changeOrigin: true },
      '/media': { target: DJANGO, changeOrigin: true },
    },
  },
});
