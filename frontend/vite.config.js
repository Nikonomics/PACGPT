import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 4005,
    proxy: {
      '/api/medicaid': {
        target: 'http://localhost:3001',
        changeOrigin: true,
      },
      '/api/alf': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/alf/, ''),
      }
    }
  }
})
