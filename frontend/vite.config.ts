import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Relative asset paths, so the built site works from any folder:
  // an S3 bucket, a GitHub Pages subpath, or opened locally.
  base: './',
  server: {
    proxy: {
      '/api/auth': 'http://127.0.0.1:8001',
      '/api/me': 'http://127.0.0.1:8001',
      '/api/watchlist': 'http://127.0.0.1:8001',
    },
  },
})
