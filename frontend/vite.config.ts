import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Relative asset paths, so the built site works from any folder:
  // an S3 bucket, a GitHub Pages subpath, or opened locally.
  base: './',
})
