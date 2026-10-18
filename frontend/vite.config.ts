/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // MapLibre loads its worker relative to its own module; pre-bundling would break that.
  optimizeDeps: { exclude: ['maplibre-gl'] },
  server: {
    // Provider calls and keys stay on the Django side; the browser only talks to /api.
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
  test: { environment: 'jsdom', globals: false },
})
