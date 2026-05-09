import { defineConfig } from 'vite'
import { fileURLToPath, URL } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) {
            return undefined;
          }
          if (id.includes('/@mui/') || id.includes('/@emotion/')) {
            return 'mui';
          }
          if (id.includes('/@radix-ui/')) {
            return 'radix';
          }
          if (id.includes('/recharts/')) {
            return 'recharts';
          }
          if (id.includes('/d3-')) {
            return 'd3';
          }
          if (id.includes('/lodash') || id.includes('/lodash-es/')) {
            return 'lodash';
          }
          return undefined;
        },
      },
    },
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  assetsInclude: ['**/*.svg', '**/*.csv'],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
