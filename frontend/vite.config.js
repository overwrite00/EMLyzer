import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    // Svuota la cartella dist ad ogni build (evita accumulo di file vecchi)
    emptyOutDir: true,
    rollupOptions: {
      output: {
        // Nomi fissi senza hash: index.js e index.css
        // Vantaggio: start.sh/bat non devono eliminare i vecchi file prima di copiare
        entryFileNames: 'assets/index.js',
        chunkFileNames:  'assets/index.js',
        assetFileNames:  'assets/index.css',
      },
    },
  },
})