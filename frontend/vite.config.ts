import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import { tanstackRouter } from '@tanstack/router-plugin/vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import { defineConfig } from 'vitest/config'

const API_TARGET = process.env.VITE_API_TARGET ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [
    // Must run before the React plugin so generated route code gets transformed.
    tanstackRouter({ target: 'react', autoCodeSplitting: true }),
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      // The service worker is a production concern; in dev it only gets in the way.
      devOptions: { enabled: false },
      includeAssets: ['favicon.svg', 'icons/apple-touch-icon.png'],
      manifest: {
        name: 'Mentor Pilot',
        short_name: 'Mentor Pilot',
        description:
          'An AI STEM mentor that guides learners from a first idea to a project ready for the science expo.',
        lang: 'en-ZA',
        start_url: '/app',
        scope: '/',
        display: 'standalone',
        orientation: 'portrait',
        background_color: '#fbfaf7',
        theme_color: '#3b43d6',
        categories: ['education'],
        icons: [
          { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
          // Full-bleed artwork, so Android can crop it to any icon shape.
          { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        // The app shell is precached so the app opens offline. Heavy on-demand
        // chunks (diagrams, charts, maths) are left out of the install and
        // cached the first time they are actually used, to save learners' data.
        globPatterns: ['**/*.{js,css,html,svg,png,woff2}'],
        maximumFileSizeToCacheInBytes: 400 * 1024,
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [/^\/api\//],
        cleanupOutdatedCaches: true,
        runtimeCaching: [
          {
            // Hashed build files never change, so the cache is always right.
            urlPattern: ({ url }) => url.pathname.startsWith('/assets/'),
            handler: 'CacheFirst',
            options: {
              cacheName: 'assets',
              expiration: { maxEntries: 80, maxAgeSeconds: 60 * 60 * 24 * 365 },
            },
          },
          {
            // Recent projects and conversations, readable offline. Network
            // first, so online learners always see fresh data.
            urlPattern: ({ url, request }) =>
              request.method === 'GET' &&
              /^\/api\/v1\/(users\/me$|projects|conversations\/[^/]+\/messages)/.test(url.pathname) &&
              !url.pathname.endsWith('.pdf'),
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-recent',
              networkTimeoutSeconds: 5,
              expiration: { maxEntries: 60, maxAgeSeconds: 60 * 60 * 24 * 7 },
              cacheableResponse: { statuses: [200] },
            },
          },
        ],
      },
    }),
  ],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      // Same-origin in the browser, so auth cookies behave as they do in prod.
      '/api': { target: API_TARGET, changeOrigin: false },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    testTimeout: 20_000,
    // e2e/ holds Playwright tests, which run in a real browser (`npm run e2e`).
    exclude: ['e2e/**', 'node_modules/**'],
    css: false,
  },
  build: {
    // FastAPI serves the built app from here in production.
    outDir: '../backend/app/static',
    emptyOutDir: true,
  },
})
