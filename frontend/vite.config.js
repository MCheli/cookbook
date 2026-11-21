import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'node:path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: [{ find: '@', replacement: path.resolve(import.meta.dirname, './src') }],
  },
  server: {
    port: 5173,
    proxy: { '/api': { target: process.env.VITE_API_TARGET || 'http://localhost:8001', changeOrigin: true } },
  },
  test: { environment: 'jsdom', include: ['tests/**/*.spec.js'] },
  build: { outDir: 'dist', emptyOutDir: true, sourcemap: false },
})
