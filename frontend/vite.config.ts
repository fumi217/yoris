import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { configDefaults, defineConfig } from 'vitest/config'

// /api はバックエンドへ中継する（同じオリジンにして CORS を開けない。spec 001 の research.md R-03）。
// docker compose では API_PROXY_TARGET=http://backend:8000（サービス名）を渡す。
const apiProxyTarget = process.env.API_PROXY_TARGET ?? 'http://localhost:8000'

// WATCH_POLLING=true なら、変更を定期的に見に行く（Windows 側のフォルダで、変更の通知がコンテナに届かないとき）
const usePolling = process.env.WATCH_POLLING === 'true'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    // tests/e2e は Playwright のテスト（npm run e2e）。Vitest では動かさない
    exclude: [...configDefaults.exclude, 'tests/e2e/**'],
  },
  server: {
    host: true,
    port: 5173,
    strictPort: true,
    // E2E のコンテナ（docker-compose.yml の e2e）が、サービス名 `frontend` で呼べるように
    allowedHosts: ['frontend'],
    watch: usePolling ? { usePolling: true, interval: 300 } : undefined,
    proxy: {
      '/api': { target: apiProxyTarget, changeOrigin: true },
    },
  },
})
