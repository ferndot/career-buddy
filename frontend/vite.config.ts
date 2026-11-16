import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// Node sets this; declared here so the config type-checks without @types/node. The dev container sets API_TARGET.
declare const process: { env: Record<string, string | undefined> }

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { '/api': { target: process.env.API_TARGET ?? 'http://127.0.0.1:8000', changeOrigin: true } },
  },
  // The built UI ships inside the Python package and is served by the API at /.
  build: { outDir: '../src/career_buddy/web/static', emptyOutDir: true },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
  },
})
