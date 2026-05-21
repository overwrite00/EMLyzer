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
        // BUGFIX: chunks devono avere nome diverso da entry file per evitare conflitti
        // Usa pattern '[name]-[hash]' per distinguere chunk dal main bundle
        chunkFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/index.css',
      },
    },
  },
})