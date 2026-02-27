import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Proxy /scan, /download, /health to FastAPI backend
      '/scan':     { target: 'http://localhost:8000', changeOrigin: true },
      '/download': { target: 'http://localhost:8000', changeOrigin: true },
      '/health':   { target: 'http://localhost:8000', changeOrigin: true },
    }
  }
})
