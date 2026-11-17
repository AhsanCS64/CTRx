import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'CTRX_DEV_');
  return {
    plugins: [react()],
    server: {
      port: 5177,
      strictPort: true,
      proxy: {
        '/api': {
          target: env.CTRX_DEV_API_TARGET || 'http://127.0.0.1:8003',
          changeOrigin: true,
        },
      },
    },
  };
});
