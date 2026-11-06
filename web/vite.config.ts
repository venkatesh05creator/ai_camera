import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['icon.svg'],
      manifest: {
        name: 'Aegis AI',
        short_name: 'Aegis',
        description: 'Local-first personal security assistant',
        theme_color: '#0f172a',
        background_color: '#0f172a',
        display: 'standalone',
        start_url: '/',
        icons: [
          { src: '/icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any' }
        ]
      },
      workbox: {
        // Cache only OUR OWN static assets (precache). Never cache /api/* —
        // those are authenticated JSON and must always come from the server.
        navigateFallbackDenylist: [/^\/api\//],
        runtimeCaching: [
          {
            urlPattern: /^http:\/\/localhost(:8000)?\/api\/.*/i,
            handler: 'NetworkOnly'
          }
        ]
      }
    })
  ],
  server: {
    // dev proxy — the backend stays on loopback only
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/healthz': 'http://127.0.0.1:8000'
    }
  },
  build: {
    outDir: 'dist',
    sourcemap: false
  }
});
