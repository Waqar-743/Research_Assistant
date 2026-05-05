import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { defineConfig, loadEnv } from 'vite';

const DEFAULT_API = 'http://localhost:8000';

function toWebSocketTarget(url: string): string {
  return url.replace(/^http/i, 'ws');
}

function normalizeUrl(value?: string): string | undefined {
  if (!value) return undefined;
  return value.trim().replace(/\/+$/, '');
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const apiTarget = normalizeUrl(env.VITE_API_URL) || DEFAULT_API;
  const wsTarget = normalizeUrl(env.VITE_WS_URL) || toWebSocketTarget(apiTarget);

  return {
    base: env.VITE_BASE || '/',
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      },
    },
    server: {
      port: 5500,
      host: '0.0.0.0',
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
        },
        '/ws': {
          target: wsTarget,
          changeOrigin: true,
          ws: true,
        },
      },
    },
  };
});
