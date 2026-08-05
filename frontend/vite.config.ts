import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react-swc';
import path from 'path';

// Environment-aware proxy targets for Docker vs local development
const API_TARGET = process.env.VITE_API_PROXY_TARGET || 'http://localhost:8000';
// For WebSocket proxy, use HTTP target (Vite upgrades to WebSocket automatically with ws: true)
const WS_TARGET = process.env.VITE_WS_PROXY_TARGET || 'http://localhost:8000';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    minify: 'esbuild',
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom'],
          charts: ['lightweight-charts'],
          query: ['@tanstack/react-query'],
        },
      },
    },
  },
  server: {
    port: 5173,
    watch: {
      // Docker Desktop bind-mounts don't emit reliable fs events on Windows —
      // poll instead so HMR works without container restarts.
      usePolling: true,
      interval: 300,
    },
    proxy: {
      '/api': {
        target: API_TARGET,
        changeOrigin: true,
      },
      '/ws/stream': {
        target: WS_TARGET,
        ws: true,
      },
    },
  },
});
