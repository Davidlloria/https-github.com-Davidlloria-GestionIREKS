import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/health': 'http://127.0.0.1:8000',
      '/customers': 'http://127.0.0.1:8000',
      '/contacts': 'http://127.0.0.1:8000',
      '/ingredients': 'http://127.0.0.1:8000',
      '/orders': 'http://127.0.0.1:8000',
      '/warehouse': 'http://127.0.0.1:8000',
      '/settings': 'http://127.0.0.1:8000',
    },
  },
})
